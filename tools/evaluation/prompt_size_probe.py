"""How many tokens one planner step costs, and whether a smaller prompt picks the same.

    python -m tools.evaluation.prompt_size_probe capture
    python -m tools.evaluation.prompt_size_probe count --label before
    (change the renderer)
    python -m tools.evaluation.prompt_size_probe count --label after

`capture` reads seven pages once and keeps what perception made of them in
`.scratch/prompt-samples.json`: three of our replicas (started here, on ports of
their own) and four public pages from the catalogue, each loaded once and only
read, after their robots.txt allows it. The replica pages are the ones that
carry perception's marks: a modal covering the course list (OVERLAY,
OCCLUDED), a cookie banner, and the train search's date picker open (a month
of INFERRED day cells).

`count` renders each sample's prompt exactly as the planner would — the
element list, and for the public pages also "What the page says", as the
open-goal planner sends it — asks the model once, and records the provider's
own count of prompt tokens and the element it chose. The same samples both
times, so the only thing that differs between `before` and `after` is the
renderer. One call per page: 7 calls a label.

The model is `OPENAI_*` from `.env` (Gemini), alone, with no fallback, so every
count is from one tokenizer. Nothing personal is in any prompt: the replicas
hold invented data and the public pages are public.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from backend.perception.serializer import Element, read_async  # noqa: E402
from tools.evaluation.conditions import banner, record  # noqa: E402

SAMPLES = REPO / ".scratch" / "prompt-samples.json"

REPLICA_PORTS = {"registration": 5291, "billing": 5292, "railways": 5293}

#: Public pages from `data/catalogue.json`, each with a goal a person might
#: bring to it. Read once each; nothing is pressed.
LIVE = [
    ("gov.uk bank holidays", "https://www.gov.uk/bank-holidays",
     "When is the next bank holiday in England and Wales?"),
    ("Wikipedia main page", "https://en.wikipedia.org/wiki/Main_Page",
     "What is today's featured article on Wikipedia?"),
    ("Weather in Lahore", "https://www.timeanddate.com/weather/pakistan/lahore",
     "What is the weather in Lahore right now?"),
    ("Forman Christian College", "https://www.fccollege.edu.pk/",
     "Find the admissions page of Forman Christian College."),
]


def _wait(url: str) -> None:
    for _ in range(150):
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"{url} did not come up")


def _element_dict(element: Element) -> dict:
    return dataclasses.asdict(element)


def _element_from(data: dict) -> Element:
    data = dict(data)
    if data.get("rect") is not None:
        data["rect"] = tuple(data["rect"])
    return Element(**data)


async def capture() -> None:
    from playwright.async_api import async_playwright

    from backend.orchestrator import robots
    from backend.orchestrator.llm_loop import render_content
    from tools.screen_site import USER_AGENT

    py = sys.executable
    servers = [
        subprocess.Popen([py, "app.py"], cwd=REPO / "replicas" / name,
                         env={**os.environ, "PORT": str(port)},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for name, port in REPLICA_PORTS.items()
    ]
    samples: list[dict] = []
    try:
        for port in REPLICA_PORTS.values():
            _wait(f"http://127.0.0.1:{port}/")
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})

            reg = f"http://127.0.0.1:{REPLICA_PORTS['registration']}"
            await page.goto(reg + "/")
            await page.get_by_role("textbox", name="Student ID or Username").fill("student")
            await page.get_by_role("textbox", name="Password").fill("x")
            await page.get_by_role("button", name="Sign In").click()
            await page.wait_for_url("**/courses")
            view = await read_async(page)
            samples.append({"name": "registration courses, modal up", "planner": "plan",
                            "goal": "Register for the course CS-401.",
                            "elements": [_element_dict(e) for e in view.elements]})

            await page.goto(f"http://127.0.0.1:{REPLICA_PORTS['billing']}/")
            view = await read_async(page)
            samples.append({"name": "billing start, cookie banner", "planner": "plan",
                            "goal": "Check my electricity bill.",
                            "elements": [_element_dict(e) for e in view.elements]})

            await page.goto(f"http://127.0.0.1:{REPLICA_PORTS['railways']}/")
            await page.locator("#date").click()
            await page.wait_for_timeout(500)
            view = await read_async(page)
            samples.append({"name": "train search, date picker open", "planner": "plan",
                            "goal": "Find trains from Lahore to Karachi on 20 November 2026.",
                            "elements": [_element_dict(e) for e in view.elements]})

            context = await browser.new_context(user_agent=USER_AGENT,
                                                viewport={"width": 1280, "height": 800})
            live = await context.new_page()
            for name, url, goal in LIVE:
                if not await robots.allowed(url):
                    print(f"{name}: robots.txt does not allow it; skipped")
                    continue
                await live.goto(url, wait_until="domcontentloaded", timeout=45000)
                await live.wait_for_timeout(2500)
                view = await read_async(live)
                samples.append({"name": name, "planner": "open", "goal": goal, "url": url,
                                "content": render_content(view.content),
                                "elements": [_element_dict(e) for e in view.elements]})
                print(f"{name}: {len(view.elements)} elements")
            await browser.close()
    finally:
        for server in servers:
            server.terminate()
            server.wait(timeout=10)
    SAMPLES.write_text(json.dumps(samples, indent=1), encoding="utf-8")
    print(f"{len(samples)} samples -> {SAMPLES.relative_to(REPO)}")


def prompt_for(sample: dict) -> tuple[str, str]:
    """The system prompt and page text the planner would send for `sample`."""
    from backend.orchestrator.llm_loop import OPEN_GOAL_RULES, SYSTEM_PROMPT, render_page

    elements = [_element_from(e) for e in sample["elements"]]
    if sample["planner"] == "open":
        page = render_page(elements) + "\n\nWhat the page says:\n" + sample["content"]
        return SYSTEM_PROMPT + OPEN_GOAL_RULES, page
    return SYSTEM_PROMPT, render_page(elements)


async def count(label: str) -> None:
    from backend.orchestrator.llm import OpenAICompatibleProvider, _load_dotenv

    _load_dotenv()
    provider = OpenAICompatibleProvider(
        api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL"),
        model=os.environ.get("OPENAI_MODEL", "gemini-3.1-flash-lite"))
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    rows = []
    for sample in samples:
        system, page = prompt_for(sample)
        before = provider.usage.prompt_tokens
        try:
            action = await provider.decide(system, page, sample["goal"])
            chose = {"action": action.action, "element_id": action.element_id,
                     "label": next((e["label"] for e in sample["elements"]
                                    if e["id"] == action.element_id), None)}
        except Exception as error:  # recorded, not raised: one page is one row
            chose = {"error": type(error).__name__}
        rows.append({
            "page": sample["name"], "elements": len(sample["elements"]),
            "page_chars": len(page), "system_chars": len(system),
            "prompt_tokens": provider.usage.prompt_tokens - before, "chose": chose,
        })
        print(json.dumps(rows[-1]))
    total = sum(r["prompt_tokens"] for r in rows)
    record(REPO / ".scratch" / f"prompt-size-{label}.json",
           {"label": label, "rows": rows, "total_prompt_tokens": total,
            "mean_prompt_tokens": round(total / len(rows), 1)})
    print(f"{label}: {total} prompt tokens over {len(rows)} steps, "
          f"mean {total / len(rows):.0f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("what", choices=["capture", "count"])
    parser.add_argument("--label", default="now")
    options = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(banner(), flush=True)
    if options.what == "capture":
        asyncio.run(capture())
    else:
        asyncio.run(count(options.label))


if __name__ == "__main__":
    main()
