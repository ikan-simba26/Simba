"""Re-ask the one decision the model got wrong. One model call, not a run.

The live run's second call was shown `option 'LAHORE CANTT'` marked INFERRED,
and the rule saying to click it, and typed into the next field instead. This
drives the page to exactly that state with Playwright and asks once more,
with the banner in place. Quota is 20 requests a day; this spends one.

Produced: EVALUATION.md 2026-09-09 "The fix: a banner, not a rule" and the
"Where information sits" experiment. **Live site, one model request.**

Moved from `.scratch/rail_llm_call2.py` on 2026-09-17, unchanged but for paths.

Run from the repo root: `python -m tools.evaluation.railways_banner_probe`.
"""

import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

from backend.orchestrator.llm import Transcript, provider_from_env
from backend.orchestrator.llm_loop import SYSTEM_PROMPT, render_page
from backend.orchestrator.railways_plan import RAILWAYS_TASK, RAILWAYS_URL
from backend.perception.serializer import read_async
from tools.evaluation.conditions import banner  # noqa: E402

UA = (
    "SIMBA-screener/0.1 (final-year university project; read-only; "
    "+https://github.com/ikan-simba26/Simba)"
)
HISTORY = ["Fill in From."]


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
        await page.goto(RAILWAYS_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        # Exactly what the loop's strategy-1 fill does, which is how the live
        # run reached this state: the direct fill times out on a readonly
        # input, the retry clicks first.
        origin = page.get_by_role("textbox", name="From", exact=True)
        await origin.click()
        await origin.press("Control+a")
        await origin.press_sequentially("LAHORE CANTT")
        await page.wait_for_timeout(1800)

        view = await read_async(page)
        rendered = render_page(view.elements)
        await browser.close()

    print("=== what the model is shown ===")
    print(rendered)
    print()

    action = await provider.decide(
        SYSTEM_PROMPT, rendered, RAILWAYS_TASK.goal, None, HISTORY
    )
    print("=== what it answered ===")
    print(f"  action     {action.action}")
    print(f"  element_id {action.element_id}")
    print(f"  value      {action.value!r}")
    print(f"  reasoning  {action.reasoning}")

    chosen = next((e for e in view.elements if e.id == action.element_id), None)
    if chosen is not None:
        print(f"\n  -> {chosen.role} {chosen.label!r} inferred={chosen.inferred}")
        correct = chosen.inferred and action.action == "click"
        print(f"  -> {'COMMITS THE CHOICE' if correct else 'DOES NOT COMMIT THE CHOICE'}")
    print("\ntranscript:", transcript.path)


asyncio.run(main())
