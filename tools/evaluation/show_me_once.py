"""Show me once (2026-11-04): a routine taught once, then run from its tile.

Produced: EVALUATION.md 2026-11-04, "Show me once" (stage 1, the bill) and
2026-11-04b (stage 2: the booking on the railways copy, and one read-only
lookup on the live train search). For each routine: the
helper's side once — how long teaching took and how many presses it needed,
and how many moves were kept — then ten runs as the person, each counted for
success, presses, checklist lines, moves, model calls and time; and on our
copies, one run against the same copy changed after teaching, which has to
stop and say so rather than press something else.

The helper here is Playwright's real mouse and keyboard on the page, through
the same recorder and perception the real window uses (`teach.py`); the
person is a script answering each screen. Headless Chromium at 1280x800, no
model, no quota. Teaching time is a script's, not a person's: it measures
SIMBA's own work while watching, which a helper adds their own time to.

The live lookup is taught once and run twice, never ten times: repeated runs
go against our copies (CLAUDE.md). It reads and never books; robots.txt is
checked first (`tools/screen_site.py`: the domain serves none).

Run from the repo root: `python -m tools.evaluation.show_me_once [runs] [bill|trains|live]...`.

`booking` (2026-11-04, `fix/show-me-once`): the booking taught once, then run
on two routes, the person choosing the train each time — Lahore Cantt to
Karachi Cantt (7UP or 8DN) and Hyderabad Jn to Sukkur, whose four trains are
none of them the 7UP the helper booked — each checked on the confirmation for
the route and the train chosen, and for one final screen with what, how much
and when on it. Written to `logs/show_me_once_fix.json`.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import replace
from pathlib import Path

from playwright.async_api import async_playwright

from backend.orchestrator import voice
from backend.orchestrator.loop import Connection, run_brief
from backend.orchestrator.routine_plan import RoutineBrief
from backend.orchestrator.routines import RoutineStore
from backend.orchestrator.teach import teach
from tools.evaluation.conditions import banner, record

ROOT = Path(__file__).resolve().parents[2]
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
REFERENCE = "04141234567890"
WHICH = set(sys.argv[2:]) or {"bill", "trains", "live"}
#: The booking's runs: the route, and the train the person chooses. Half on a
#: route whose trains are not the helper's 7UP (2026-11-04, fix).
BOOKINGS = [("Lahore Cantt", "Karachi Cantt", train) for train in
            ("7UP", "8DN", "7UP", "8DN", "7UP")] + [
            ("Hyderabad Jn", "Sukkur", train) for train in
            ("11UP", "12DN", "13UP", "14DN", "13UP")]
LIVE = "https://www.pakrailways.gov.pk/train"
#: What the person says when asked, by the box's name.
SAYS = {"Reference No.": REFERENCE, "From": "Lahore Cantt", "To": "Karachi Cantt",
        "Passenger Name": "Bilal Ahmed"}
#: The billing copy as it is, and as it is after its search button was renamed;
#: the railways copy.
BILLING, CHANGED, RAILWAYS = 5141, 5142, 5241


class Helper(Connection):
    """The overlay's side while a helper teaches: what the backend sent, and
    what the script has the bar say."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.incoming: asyncio.Queue = asyncio.Queue()
        self.presses = 0

    async def send(self, message_type, payload) -> None:
        self.sent.append((message_type, json.loads(payload.model_dump_json())))

    async def next_message(self) -> dict:
        return await self.incoming.get()

    def say(self, message_type: str, payload: dict) -> None:
        self.presses += 1
        self.incoming.put_nowait({"type": message_type, "payload": payload})

    def bar(self) -> dict:
        return [p for n, p in self.sent if n == "teach.watching"][-1]

    async def until(self, ready, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        while not ready():
            if time.monotonic() > deadline:
                raise TimeoutError([n for n, _ in self.sent])
            await asyncio.sleep(0.05)


async def teach_the_bill(store: RoutineStore) -> dict:
    """The bill, shown once on the billing copy, as `test_teach.py` shows it."""
    helper = Helper()
    page_presses = 0
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        started = time.monotonic()
        job = asyncio.create_task(teach(page, helper, f"http://127.0.0.1:{BILLING}", store))
        await helper.until(lambda: any(n == "teach.watching" for n, _ in helper.sent))
        await page.get_by_role("button", name="Accept all cookies").click()
        await page.get_by_role("textbox", name="Reference No.").fill(REFERENCE)
        await page.get_by_role("button", name="Check Bill").click()
        page_presses += 3
        await page.wait_for_url("**/bill")
        await helper.until(lambda: helper.bar()["question"] is not None)
        helper.say("teach.answer", {"action": "ask", "step": helper.bar()["question"]["step"]})
        await helper.until(lambda: helper.bar()["question"] is None)
        helper.say("teach.answer", {"action": "finish"})
        await helper.until(lambda: helper.bar()["pointing"])
        await page.get_by_text("14,382", exact=True).first.click()
        page_presses += 1
        await helper.until(lambda: any(n == "step.presented" for n, _ in helper.sent))
        readback = [p for n, p in helper.sent if n == "step.presented"][0]["routine"]
        helper.say("step.response", {"step_index": 1, "action_id": "confirm",
                                     "input_values": {"name": "My bill", "answer": "Amount due"}})
        kept = await asyncio.wait_for(job, 30)
        seconds = time.monotonic() - started
        await browser.close()
    return {"routine": kept, "seconds": round(seconds, 1), "moves": len(kept.steps),
            "asked_each_time": len(kept.asks), "helper_presses_on_page": page_presses,
            "helper_presses_on_bar": helper.presses, "read_back": readback}


async def _station(page, box: str, typed: str, station: str) -> None:
    field = page.locator(f"input[placeholder='{box}'], #{box.lower()}").first
    await field.click()
    await field.press_sequentially(typed, delay=40)
    option = page.locator("li:visible", has_text=station).first
    await option.wait_for(timeout=20000)
    await option.click()
    await page.wait_for_function(
        f"[...document.querySelectorAll('input')].some(i => i.value.includes({station!r}))")


async def _answer(helper: Helper, same: bool) -> None:
    await helper.until(lambda: helper.bar()["question"] is not None)
    helper.say("teach.answer", {"action": "same" if same else "ask",
                                "step": helper.bar()["question"]["step"]})
    await helper.until(lambda: helper.bar()["question"] is None)


def results_cells(live: bool) -> str:
    """The results' cells: the live site's table body is a table of its own,
    apart from its headings (EVALUATION.md, 2026-09-17i); our copy's is in
    #results. Never the calendar's cells, which are table cells too."""
    return ".el-table__body-wrapper tbody td" if live else "#results tbody td"


async def _search_trains(page, helper: Helper, live: bool) -> None:
    """From, To, a day on the calendar, the search: as a helper does it on the
    train search: eight presses on the page (two boxes, two choices, the date
    box, the next month, the day, and the search)."""
    await _station(page, "From", "LAH", "LAHORE CANTT")
    await _answer(helper, False)
    await _station(page, "To", "KARACHI", "KARACHI CANTT")
    await _answer(helper, False)
    date_box = page.locator("input[placeholder='Departure Date'], #date").first
    await date_box.click()
    banner = (".el-date-picker__header" if live else "#showing")
    await page.locator(banner).first.wait_for()
    before = await page.locator(banner).first.inner_text()
    await page.get_by_role("button", name="Next Month").first.click()
    await page.wait_for_function(
        f"document.querySelector({banner!r}).innerText !== {before!r}")
    day = page.locator("td.available:visible", has_text="15").first
    await day.click()
    await _answer(helper, False)
    # The search button has no name: the one visible button with none, outside
    # the calendar. Pressed with the mouse, as a helper would.
    button = await page.evaluate_handle("""() => [...document.querySelectorAll('button')]
        .find(b => b.offsetParent && !(b.innerText || '').trim()
              && !b.getAttribute('aria-label') && !b.closest('.el-picker-panel'))""")
    await button.as_element().click()
    await page.locator(results_cells(live)).first.wait_for(timeout=60000)


async def teach_trains(store: RoutineStore, live: bool) -> dict:
    """The train search, shown once: on our copy as far as a booking, on the
    live site as far as the trains, which are pointed at."""
    helper = Helper()
    url = LIVE if live else f"http://127.0.0.1:{RAILWAYS}"
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        started = time.monotonic()
        job = asyncio.create_task(teach(page, helper, url, store))
        await helper.until(lambda: any(n == "teach.watching" for n, _ in helper.sent), 60)
        await _search_trains(page, helper, live)
        page_presses = 8
        if live:
            helper.say("teach.answer", {"action": "finish"})
            await helper.until(lambda: helper.bar()["pointing"])
            await page.locator(results_cells(live)).first.click()
            page_presses += 1
            name, answer = "Trains to Karachi", "Trains"
        else:
            await page.locator("#results a").first.click()
            await page.wait_for_url("**/book**")
            await page.locator("#passenger").fill("Ayesha Khan")
            await page.get_by_label("AC Standard").click()
            await page.wait_for_function(
                "document.querySelector('input[value=\"AC Standard\"]').checked")
            await _answer(helper, False)
            await page.get_by_role("button", name="Confirm Booking").click()
            await page.get_by_role("heading", name="Booking Confirmed").wait_for()
            helper.say("teach.answer", {"action": "finish"})
            await helper.until(lambda: helper.bar()["pointing"])
            await page.locator("td", has_text="PR-").first.click()
            page_presses += 5
            name, answer = "Book my train", "Booking number"
        await helper.until(lambda: any(n == "step.presented" for n, _ in helper.sent), 60)
        readback = [p for n, p in helper.sent if n == "step.presented"][0]["routine"]
        helper.say("step.response", {"step_index": 1, "action_id": "confirm",
                                     "input_values": {"name": name, "answer": answer}})
        kept = await asyncio.wait_for(job, 60)
        seconds = time.monotonic() - started
        await browser.close()
    return {"routine": kept, "seconds": round(seconds, 1), "moves": len(kept.steps),
            "asked_each_time": len(kept.asks), "helper_presses_on_page": page_presses,
            "helper_presses_on_bar": helper.presses, "read_back": readback}


class Person(Connection):
    """Answers each screen as a person would: the number when asked, Yes to
    cookies, and counts what was shown."""

    def __init__(self, says: dict | None = None, train: str | None = None) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.says = {**SAYS, **(says or {})}
        self.train = train

    async def send(self, message_type, payload) -> None:
        self.sent.append((message_type, json.loads(payload.model_dump_json())))

    async def poll(self, seconds: float = 0.0) -> list[dict]:  # noqa: ARG002
        return []

    async def receive(self, message_type, step_index=None, on_other=None) -> dict:  # noqa: ARG002
        step = [p for n, p in self.sent if n == "step.presented"][-1]
        values = {f["id"]: self.says.get(f["label"], "") for f in step["fields"]
                  if f["id"].startswith("value")}
        action = "confirm"
        if step["instruction"] == voice.which_row("Train No.") and self.train:
            labels = [a["label"] for a in step["actions"]]
            action = f"{voice.CHOICE_PREFIX}" + str(next(
                i for i, label in enumerate(labels) if label.split(",")[0] == self.train))
        if step["instruction"] == voice.ROUTINE_TRY:
            # The offer of a model, if one is set up: no, as a person who
            # wants only what the helper showed would say.
            action = voice.DECLINE_ID
        elif step["instruction"] == voice.ASK_ROUTINE_DAY:
            action = f"{voice.CHOICE_PREFIX}1"  # Tomorrow
        elif step["instruction"] == voice.ASK_CLOSEST:
            labels = [a["label"] for a in step["actions"]]
            action = f"{voice.CHOICE_PREFIX}{labels.index('LAHORE CANTT')}"
        return {"type": "step.response", "payload": {
            "step_index": step_index, "action_id": action, "input_values": values}}

    def of(self, kind: str) -> list[dict]:
        return [p for n, p in self.sent if n == kind]


#: The confirmation's own summary, header by header.
SUMMARY_JS = ("() => Object.fromEntries([...document.querySelectorAll('tr')]"
              ".filter(r => r.querySelector('th') && r.querySelector('td'))"
              ".map(r => [r.querySelector('th').innerText.trim(),"
              " r.querySelector('td').innerText.trim()]))")


async def one(routine, person: "Person | None" = None) -> dict:
    person = person or Person()
    started = time.monotonic()
    page_says: dict = {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            await run_brief(page, person, RoutineBrief(routine), routine.start, auto=True)
            if person.train:
                page_says = await page.evaluate(SUMMARY_JS)
        finally:
            await browser.close()
    shown = person.of("step.presented")
    end = (person.of("task.completed") or [None])[-1]
    stuck = (person.of("help.requested") or [None])[-1]
    return {
        "completed": end is not None,
        "answer": end["findings"][0]["values"] if end and end["findings"] else None,
        "final_screens": sum(1 for s in shown if s.get("final")),
        "proof": bool(end and end.get("proof")),
        "presses": sum(1 for s in shown if s["requires_confirmation"]),
        "checklist_lines": sum(1 for s in shown if not s["requires_confirmation"]),
        "steps_taken": end["steps_taken"] if end else None,
        "llm_calls": end["llm_calls"] if end else 0,
        "seconds": round(time.monotonic() - started, 1),
        "stopped_because": stuck["reason"] if stuck else None,
        "which_train_asked": any(s["instruction"] == voice.which_row("Train No.") for s in shown),
        "final_details": [[d["label"] for d in s["final"]] for s in shown if s.get("final")],
        "booked": {k: page_says.get(k) for k in ("Train", "From", "To", "Fare")}
        if page_says else None,
    }


def serve() -> list[subprocess.Popen]:
    procs = []
    for site, port, label in (("billing", BILLING, None), ("billing", CHANGED, "Find my bill"),
                              ("railways", RAILWAYS, None)):
        env = {**os.environ, "PORT": str(port)}
        if label:
            env["BILLING_CHECK_LABEL"] = label
        procs.append(subprocess.Popen([sys.executable, "app.py"], cwd=ROOT / "replicas" / site,
                                      env=env, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL))
    for port in (BILLING, CHANGED, RAILWAYS):
        deadline = time.time() + 30
        while True:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=1)
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.2)
    return procs


def summarise(taught: dict, runs: list[dict], right) -> dict:
    seconds = sorted(r["seconds"] for r in runs)
    return {
        "teaching": taught,
        "runs": len(runs),
        "completed": sum(r["completed"] for r in runs),
        "right_answer": sum(bool(right(r["answer"])) for r in runs),
        "with_proof": sum(r["proof"] for r in runs),
        "presses": sorted({r["presses"] for r in runs}),
        "final_screens": sorted({r["final_screens"] for r in runs}),
        "checklist_lines": sorted({r["checklist_lines"] for r in runs}),
        "steps_taken": sorted({r["steps_taken"] for r in runs}),
        "llm_calls": sorted({r["llm_calls"] for r in runs}),
        "seconds_mean": round(sum(seconds) / len(seconds), 2),
        "seconds_range": [seconds[0], seconds[-1]],
        "stopped": [r["stopped_because"] for r in runs if r["stopped_because"]],
    }


def main() -> None:
    print(banner(), flush=True)
    store = RoutineStore(ROOT / ".scratch" / "show-me-once" / "eval-routines.json")
    store.clear()
    procs = serve()
    summary: dict = {}
    every: dict = {}
    try:
        plans = []
        if "bill" in WHICH:
            plans.append(("bill on the billing copy", lambda: teach_the_bill(store), RUNS,
                          lambda answer: answer == ["14,382"]))
        if "trains" in WHICH:
            plans.append(("booking on the railways copy",
                          lambda: teach_trains(store, live=False), RUNS,
                          lambda answer: bool(answer) and answer[0].startswith("PR-")))
        if "live" in WHICH:
            plans.append(("trains on the live site, read only",
                          lambda: teach_trains(store, live=True), min(RUNS, 2),
                          lambda answer: bool(answer)))
        if "booking" in WHICH:
            booking(store, summary, every)
        for name, teaching, count, right in plans:
            taught = asyncio.run(teaching())
            routine = taught.pop("routine")
            print(json.dumps({name: taught}), flush=True)
            runs = []
            for run in range(1, count + 1):
                result = asyncio.run(one(routine))
                result["run"] = run
                runs.append(result)
                print(json.dumps(result), flush=True)
            summary[name] = summarise(taught, runs, right)
            every[name] = runs
            if name.startswith("bill"):
                changed = asyncio.run(one(replace(routine, start=f"http://127.0.0.1:{CHANGED}")))
                print(json.dumps({"changed": changed}), flush=True)
                summary[name]["changed_after_teaching"] = changed
            store.clear()
    finally:
        for proc in procs:
            proc.terminate()
            proc.wait(timeout=10)
        store.clear()
    print(json.dumps(summary, indent=1))
    log = "show_me_once_fix.json" if WHICH == {"booking"} else "show_me_once.json"
    record(ROOT / "logs" / log, {"runs": every, "summary": summary})


def booking(store: RoutineStore, summary: dict, every: dict) -> None:
    """The booking taught once, then each of `BOOKINGS` as the person."""
    from backend.orchestrator.details import match_station

    name = "booking on the railways copy, the person's train"
    taught = asyncio.run(teach_trains(store, live=False))
    routine = taught.pop("routine")
    print(json.dumps({name: taught}), flush=True)
    runs = []
    for run, (origin, destination, train) in enumerate(BOOKINGS[:RUNS], start=1):
        person = Person({"From": origin, "To": destination}, train)
        result = asyncio.run(one(routine, person))
        booked = result["booked"] or {}
        stations = [match_station(place, [booked.get("From") or "", booked.get("To") or ""])
                    for place in (origin, destination)]
        result.update(run=run, route=f"{origin} to {destination}", wanted=train,
                      right_train=booked.get("Train") == train,
                      right_route=all(s.station for s in stations))
        runs.append(result)
        print(json.dumps(result), flush=True)
    summary[name] = summarise(taught, runs, lambda answer: bool(answer)
                              and answer[0].startswith("PR-"))
    summary[name]["right_train_and_route"] = sum(r["right_train"] and r["right_route"]
                                                for r in runs)
    summary[name]["which_train_asked"] = sum(r["which_train_asked"] for r in runs)
    summary[name]["final_details"] = sorted({tuple(d) for r in runs
                                             for d in r["final_details"]})
    every[name] = runs
    store.clear()


if __name__ == "__main__":
    main()
