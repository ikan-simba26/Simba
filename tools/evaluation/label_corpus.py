"""How hard each corpus page is for the agent — the first `y` beside the `X`.

`data/corpus.json` says what 50 pages are like. It says nothing about whether
SIMBA can get through them, and a training set needs both. This runs the
hardcoded planner over every page that has a plan and records what the run
cost, page by page, into `data/labels.json`.

**Raw measurements, no score.** There is no "difficulty: 0.7" here, for the
same reason `page_features` has no weights: a score chosen before there is
enough data to fit one decides what the data is allowed to say (DECISIONS.md,
"The estimator measures before it scores"). What comes back is steps, retries,
verification failures, seconds, and whether recovery fired — each a count of
something that happened.

**Most pages get no label at all, and that is the point of running it.** Plans
exist for four flows. Everything else in the corpus is a page nobody has
written a plan for, and those rows say so explicitly rather than being left
out — a training set with the unlabelled rows quietly dropped looks far
healthier than it is.

**Three runs per replica, one against the live site.** CLAUDE.md: repeated
benchmark runs go against local replicas, never a live site. One run is a
measurement; ten would be hammering someone's public timetable. The row
records `runs`, so a label built on one sample cannot be mistaken for a label
built on three.

What is counted, and where each number comes from:

| Field | Where |
|---|---|
| `steps_taken` | `task.completed`, or the number of steps presented if it never arrived |
| `attempts` | every call into `attempt_move` |
| `retries` | those calls made with `strategy=1` — the second try at the same move |
| `verification_failures` | every `verify` that came back with a reason |
| `step_failures` | `step.failed` — both strategies exhausted on one move |
| `recovery_triggered` | any `step.failed` at all: the planner was told and continued |
| `gave_up` | `help.requested` — two setbacks in a row, or a durability failure |
| `seconds` | wall clock around the whole run, which reads ±2x on this machine |

`attempts` and `retries` are read by wrapping the loop's own functions rather
than by parsing messages, because a retry that *succeeds* sends no message at
all — the loop only announces a move when both strategies have failed. A
harness that counted `step.failed` would report zero retries on a run that
retried four times and recovered.

Run it, from the repo root, with the replicas free:

    python -m tools.evaluation.label_corpus
"""

import asyncio
import statistics
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

from backend.orchestrator import loop as loop_module
from backend.orchestrator.billing_plan import BILLING_PLAN, BILLING_TASK
from backend.orchestrator.llm_loop import REGISTRATION_TASK
from backend.orchestrator.loop import Connection, run_task
from backend.orchestrator.plan import REGISTRATION_PLAN, HardcodedPlanner
from backend.orchestrator.railways_plan import RAILWAYS_PLAN, RAILWAYS_TASK
from backend.orchestrator.stubborn_plan import STUBBORN_PLAN, STUBBORN_TASK
from backend.perception.serializer import VIEWPORT
from tools.evaluation.collect_corpus import BILLING, REGISTRATION, replicas_running
from tools.evaluation.conditions import banner, record

REPO_ROOT = Path(__file__).resolve().parents[2]
RAILWAYS_URL = "https://www.pakrailways.gov.pk/train"

#: Repeats. Local replicas can take three; the live site gets one.
RUNS_LOCAL = 3
RUNS_LIVE = 1

#: Credentials for the one flow that asks for them. The replica accepts
#: anything; these are the strings every other script here uses.
CREDENTIALS = {"username": "raham", "password": "hunter2"}

#: `(name, plan, task, start_url, runs)`. A corpus row is labelled when its
#: URL is one of these start URLs.
FLOWS = [
    ("registration", REGISTRATION_PLAN, REGISTRATION_TASK, f"{REGISTRATION}/",
     RUNS_LOCAL),
    ("stubborn", STUBBORN_PLAN, STUBBORN_TASK, f"{REGISTRATION}/stubborn",
     RUNS_LOCAL),
    ("billing", BILLING_PLAN, BILLING_TASK, f"{BILLING}/", RUNS_LOCAL),
    ("railways", RAILWAYS_PLAN, RAILWAYS_TASK, RAILWAYS_URL, RUNS_LIVE),
]


class Counting(Connection):
    """A frontend that always confirms, and remembers everything it was sent.

    Field values are echoed back from `step.presented` rather than supplied
    from a table, so a plan that prefills a reference number needs nothing
    added here. Only genuinely empty fields — the credentials — are filled
    from `CREDENTIALS`, and a missing one is left empty rather than guessed
    at, so the run fails honestly instead of on a typo in this file.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.fields_by_step: dict[int, dict[str, str]] = {}

    async def send(self, message_type: str, payload) -> None:
        body = payload.model_dump()
        self.sent.append((message_type, body))
        if message_type == "step.presented":
            values = {}
            for field in body.get("fields", []) or []:
                value = field.get("value") or CREDENTIALS.get(field["id"], "")
                values[field["id"]] = value
            self.fields_by_step[body.get("step_index", len(self.fields_by_step))] = values

    async def receive(self, message_type: str, step_index=None, on_other=None) -> dict:
        return {
            "type": "step.response",
            "payload": {
                "step_index": step_index,
                "action_id": "confirm",
                "input_values": self.fields_by_step.get(step_index, {}),
            },
        }

    def of(self, message_type: str) -> list[dict]:
        return [body for name, body in self.sent if name == message_type]


class Instrumented:
    """Wraps the loop's own functions to count what messages cannot show.

    A retry that succeeds sends nothing, so `step.failed` undercounts. These
    wrappers sit on the module attributes `run_task` resolves at call time,
    are installed for exactly one run, and are removed afterwards.
    """

    def __init__(self) -> None:
        self.attempts = 0
        self.retries = 0
        self.verification_failures = 0
        self.failures: list[str] = []
        self._attempt_move = loop_module.attempt_move
        self._verify = loop_module.verify

    def __enter__(self) -> "Instrumented":
        async def attempt_move(page, move, input_values, strategy, before):
            self.attempts += 1
            if strategy >= 1:
                self.retries += 1
            failure = await self._attempt_move(page, move, input_values, strategy, before)
            if failure is not None:
                self.failures.append(failure)
            return failure

        async def verify(page, before, expect):
            failure = await self._verify(page, before, expect)
            if failure is not None:
                self.verification_failures += 1
            return failure

        loop_module.attempt_move = attempt_move
        loop_module.verify = verify
        return self

    def __exit__(self, *_) -> None:
        loop_module.attempt_move = self._attempt_move
        loop_module.verify = self._verify


async def one_run(browser, plan, task, start_url: str, index: int) -> dict:
    """One whole task, start to finish, with everything it cost."""
    connection = Counting()
    page = await browser.new_page(
        viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})
    started = time.monotonic()
    error: str | None = None
    with Instrumented() as counted:
        try:
            await run_task(page, connection, HardcodedPlanner(plan), task, start_url)
        except Exception as raised:  # noqa: BLE001 - a crash is a result too
            error = f"{type(raised).__name__}: {str(raised)[:160]}"
    seconds = round(time.monotonic() - started, 1)
    final_url = page.url
    await page.close()

    completed = connection.of("task.completed")
    presented = connection.of("step.presented")
    step_failures = connection.of("step.failed")
    help_requested = connection.of("help.requested")
    return {
        "run": index,
        "completed": bool(completed),
        "steps_taken": completed[0]["steps_taken"] if completed else len(presented),
        "attempts": counted.attempts,
        "retries": counted.retries,
        "verification_failures": counted.verification_failures,
        "step_failures": len(step_failures),
        "recovery_triggered": bool(step_failures),
        "gave_up": bool(help_requested),
        "gave_up_reason": help_requested[0]["reason"] if help_requested else None,
        "seconds": seconds,
        "final_url": final_url,
        "error": error,
        "failures": counted.failures,
    }


def summarise(name: str, runs: list[dict]) -> dict:
    """The runs, as one label, with the spread kept.

    Medians rather than means: three runs is few enough that one slow one
    moves a mean and not a median, and wall clock on this machine reads ±2x
    (EVALUATION.md, 2026-09-17h).
    """
    def across(field: str) -> dict:
        values = [run[field] for run in runs]
        return {"median": statistics.median(values),
                "min": min(values), "max": max(values)}

    return {
        "flow": name,
        "runs": len(runs),
        "completed": sum(1 for run in runs if run["completed"]),
        "pass_rate": round(sum(1 for r in runs if r["completed"]) / len(runs), 3),
        "steps_taken": across("steps_taken"),
        "attempts": across("attempts"),
        "retries": across("retries"),
        "verification_failures": across("verification_failures"),
        "step_failures": across("step_failures"),
        "recovery_triggered": any(run["recovery_triggered"] for run in runs),
        "gave_up": sum(1 for run in runs if run["gave_up"]),
        "seconds": across("seconds"),
        "each_run": runs,
    }


async def measure() -> dict[str, dict]:
    labels: dict[str, dict] = {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        for name, plan, task, start_url, repeats in FLOWS:
            runs = []
            for index in range(1, repeats + 1):
                result = await one_run(browser, plan, task, start_url, index)
                runs.append(result)
                mark = "OK  " if result["completed"] else "FAIL"
                print(f"  [{mark}] {name:<13} run {index}/{repeats}  "
                      f"steps={result['steps_taken']} "
                      f"retries={result['retries']} "
                      f"verify_fail={result['verification_failures']} "
                      f"{result['seconds']}s", flush=True)
            labels[start_url] = summarise(name, runs)
        await browser.close()
    return labels


# --- joining the labels to the corpus ---------------------------------------


#: The nine features a page gets whether or not anyone can drive it. Copied
#: into every row so a label file can be read on its own.
FEATURES = ["interactive", "links", "inferred", "text_density", "max_depth",
            "overlays", "form_fields", "dead_link_ratio", "reading_grade"]


def join(corpus_rows: list[dict], labels: dict[str, dict]) -> list[dict]:
    """One row per corpus page, labelled where a plan reaches it.

    A page is labelled when a flow *starts* there. A page the flow walks
    through on its way — the course list behind the login, say — is marked
    `visited_during` and given no difficulty of its own, because a task-level
    measurement cannot be split across the pages it crossed without
    attributing each step to a page, which this does not do.
    """
    visited: dict[str, str] = {}
    for start_url, label in labels.items():
        for run in label["each_run"]:
            if run["final_url"] and run["final_url"] != start_url:
                visited.setdefault(run["final_url"], label["flow"])

    out = []
    for row in corpus_rows:
        entry = {
            "url": row["url"],
            "state": row.get("state"),
            "kind": row.get("kind"),
            "features": ({f: row[f] for f in FEATURES}
                         if "error" not in row else None),
        }
        label = labels.get(row["url"])
        # Only the row read in its undriven state gets the label: a driven
        # state is a different page, and the flow started on the plain one.
        if label is not None and row.get("state") == "as it loads":
            entry["label_source"] = "agent_run"
            entry["difficulty"] = {k: v for k, v in label.items() if k != "each_run"}
        elif label is not None:
            entry["label_source"] = "driven_state_of_a_labelled_page"
            entry["difficulty"] = None
            entry["note"] = (f"the {label['flow']} flow starts at this URL, but "
                             f"this row is the page after {row.get('state')!r}")
        elif row["url"] in visited:
            entry["label_source"] = "visited_during"
            entry["difficulty"] = None
            entry["note"] = f"a {visited[row['url']]} run ended here"
        else:
            entry["label_source"] = "features_only"
            entry["difficulty"] = None
            entry["note"] = "no plan exists for this page, so nothing has driven it"
        out.append(entry)
    return out


def report(rows: list[dict], labels: dict[str, dict]) -> None:
    by_source: dict[str, int] = {}
    for row in rows:
        by_source[row["label_source"]] = by_source.get(row["label_source"], 0) + 1

    print(f"\n=== {len(rows)} corpus pages ===")
    for source, count in sorted(by_source.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>3}  {source}")
    usable = by_source.get("agent_run", 0)
    print(f"\n  Usable difficulty labels: {usable} of {len(rows)} "
          f"({usable / len(rows):.1%})")

    print("\n=== the difficulty that was measured ===")
    print(f"{'flow':<14}{'runs':>5}{'pass':>6}{'steps':>7}{'attempts':>10}"
          f"{'retries':>9}{'verify fail':>13}{'recovered':>11}{'seconds':>9}")
    for label in labels.values():
        print(f"{label['flow']:<14}{label['runs']:>5}"
              f"{label['pass_rate']:>6.0%}"
              f"{label['steps_taken']['median']:>7.0f}"
              f"{label['attempts']['median']:>10.0f}"
              f"{label['retries']['median']:>9.0f}"
              f"{label['verification_failures']['median']:>13.0f}"
              f"{'yes' if label['recovery_triggered'] else 'no':>11}"
              f"{label['seconds']['median']:>9.1f}")


async def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    corpus_path = REPO_ROOT / "data" / "corpus.json"
    if not corpus_path.exists():
        raise SystemExit("no data/corpus.json — run collect_corpus first")
    import json
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    corpus_rows = corpus["results"]["headless"]

    print(banner(), flush=True)
    print(f"{len(FLOWS)} flows over {len(corpus_rows)} corpus pages, "
          f"hardcoded planner, no model\n", flush=True)

    with replicas_running():
        labels = await measure()

    rows = join(corpus_rows, labels)
    out = REPO_ROOT / "data" / "labels.json"
    record(out, {"pages": rows, "flows": labels},
           corpus_taken_at=corpus["conditions"].get("taken_at"),
           corpus_pages=len(corpus_rows),
           runs_local=RUNS_LOCAL, runs_live=RUNS_LIVE,
           labelled=sum(1 for r in rows if r["label_source"] == "agent_run"),
           viewport=list(VIEWPORT))
    print(f"\nwrote {out}", flush=True)
    report(rows, labels)


if __name__ == "__main__":
    asyncio.run(main())
