"""Re-ask the one decision the model got wrong, with the setback promoted.

Call 7 of the 2026-09-09 run was told, in plain words at the end of its
prompt, that the date it had set was the wrong month and that the choice
needed committing. It clicked search anyway. This drives the page to exactly
that state with Playwright and asks once more, with the feedback moved above
the element list. One model call.

Produced: EVALUATION.md 2026-09-09b, "The setback reached the model and the
model ignored it" — the re-asked call with the setback promoted. **Live
site, one model request.** It commits both stations and sets a date on the
live form; nothing is submitted.

Moved from `.scratch/rail_llm_call7.py` on 2026-09-17, unchanged but for paths.

Run from the repo root: `python -m tools.evaluation.railways_setback_probe`.
"""

import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

from backend.orchestrator.llm import Transcript, build_user_prompt, provider_from_env
from backend.orchestrator.llm_loop import SYSTEM_PROMPT, render_page
from backend.orchestrator.railways_plan import RAILWAYS_TASK, RAILWAYS_URL
from backend.perception.serializer import read_async
from tools.evaluation.conditions import banner  # noqa: E402

UA = (
    "SIMBA-screener/0.1 (final-year university project; read-only; "
    "+https://github.com/ikan-simba26/Simba)"
)
HISTORY = [
    "Fill in From.",
    "Click LAHORE CANTT.",
    "Fill in To.",
    "Click KARACHI CANTT.",
    "Fill in Departure Date.",
    "Click 15.",
]
SETBACK = (
    "'Departure Date' no longer holds what I put in it — it held "
    "'2026-10-15' and now holds '15-09-2026'. Typing a value is not always "
    "choosing it — a list or a calendar may need the choice committed by "
    "clicking the option itself. Put it back, and commit it this time."
)


async def commit_station(page, field: str, typed: str, wanted: str) -> None:
    box = page.get_by_role("textbox", name=field, exact=True)
    await box.click()
    await box.press("Control+a")
    await box.press_sequentially(typed)
    await page.wait_for_timeout(1600)
    view = await read_async(page)
    option = next(
        e for e in view.elements if e.inferred and e.label == wanted
    )
    await page.locator(option.locator_hint).click()
    await page.wait_for_timeout(700)


async def main() -> None:
    print(banner(), flush=True)
    transcript = Transcript()
    provider = provider_from_env(transcript=transcript)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            user_agent=UA, viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        page.set_default_timeout(15000)
        await page.goto(RAILWAYS_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        await commit_station(page, "From", "LAHORE CANTT", "LAHORE CANTT")
        await commit_station(page, "To", "KARACHI CANTT", "KARACHI CANTT")

        # Step 5 and 6 as the model actually did them: type the date, then
        # click the 15th of the month the picker opened on.
        date_field = page.get_by_role("textbox", name="Departure Date", exact=True)
        await date_field.click()
        await date_field.press("Control+a")
        await date_field.press_sequentially("2026-10-15")
        await page.wait_for_timeout(900)
        view = await read_async(page)
        wrong = next(
            e for e in view.elements
            if e.inferred and e.label == "15" and e.qualifier == ""
        )
        await page.locator(wrong.locator_hint).click()
        await page.wait_for_timeout(900)

        print("state reproduced:")
        for name in ("From", "To", "Departure Date"):
            value = await page.get_by_role(
                "textbox", name=name, exact=True
            ).input_value()
            print(f"   {name:15} = {value!r}")

        view = await read_async(page)
        rendered = render_page(view.elements)
        await browser.close()

    prompt = build_user_prompt(rendered, RAILWAYS_TASK.goal, SETBACK, HISTORY)
    print("\n=== first 6 lines of the prompt ===")
    print("\n".join(prompt.splitlines()[:6]))

    action = await provider.decide(
        SYSTEM_PROMPT, rendered, RAILWAYS_TASK.goal, SETBACK, HISTORY
    )
    print("\n=== what it answered ===")
    print(f"  action     {action.action}")
    print(f"  element_id {action.element_id}")
    print(f"  reasoning  {action.reasoning}")

    chosen = next((e for e in view.elements if e.id == action.element_id), None)
    if chosen is not None:
        print(f"\n  -> {chosen.role} {chosen.label!r}")
        fixes = chosen.label in {"Next Month", "Departure Date"} or (
            chosen.role == "option"
        )
        print(f"  -> {'ADDRESSES THE DATE' if fixes else 'MOVES ON REGARDLESS'}")
    print("\ntranscript:", transcript.path)


asyncio.run(main())
