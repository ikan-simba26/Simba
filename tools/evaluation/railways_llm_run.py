"""One LLM-planned railways run against the live site.

The first time the model sees inferred elements, and the first LLM run on a
site nobody wrote for us. One run: the free quota does not allow more.

Produced: EVALUATION.md 2026-09-09 runs 1 and 2, 2026-09-09b, and the
2026-09-17 owed run. **Live site and model quota**: one run is 6-8
requests. The transcript goes to `logs/llm-<timestamp>.jsonl`.

Moved from `.scratch/rail_llm.py` on 2026-09-17, unchanged but for paths.

Run from the repo root: `python -m tools.evaluation.railways_llm_run`.
"""

import asyncio
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright

from backend.orchestrator.llm import Transcript, provider_from_env
from backend.orchestrator.llm_loop import LLMPlanner, render_page
from backend.orchestrator.loop import Connection, run_task
from backend.orchestrator.railways_plan import (
    RAILWAYS_TASK,
    RAILWAYS_URL,
)
from backend.perception.serializer import read_async
from tools.evaluation.conditions import banner  # noqa: E402

UA = (
    "SIMBA-screener/0.1 (final-year university project; read-only; "
    "+https://github.com/ikan-simba26/Simba)"
)


class Printing(Connection):
    def __init__(self) -> None:
        self.seq = 0
        self.sent: list[tuple[str, dict]] = []

    async def send(self, message_type: str, payload) -> None:
        self.seq += 1
        data = payload.model_dump()
        self.sent.append((message_type, data))
        if message_type == "step.presented":
            print(f"[{self.seq:2}] step {data['step_index']}/{data['step_total']}: "
                  f"{data['instruction']}")
            print(f"                 reasoning: {data['detail']}")
        elif message_type == "step.failed":
            print(f"[{self.seq:2}] STEP FAILED {data['step_index']}: {data['reason']}")
        elif message_type == "state.changed":
            pass
        else:
            print(f"[{self.seq:2}] {message_type}: {data}")

    async def receive(self, message_type, step_index=None, on_other=None):
        return {
            "type": "step.response",
            "payload": {
                "step_index": step_index,
                "action_id": "confirm",
                "input_values": {},
            },
        }


async def main() -> None:
    print(banner(), flush=True)
    transcript = Transcript()
    print("transcript:", transcript.path)
    provider = provider_from_env(transcript=transcript)
    print("provider:", provider.name, getattr(provider, "_model", "?"))
    print("goal:", RAILWAYS_TASK.goal)
    print()

    planner = LLMPlanner(provider, RAILWAYS_TASK)
    connection = Printing()
    started = time.monotonic()
    requests: list[tuple[str, str]] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            user_agent=UA, viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        page.on(
            "request",
            lambda r: requests.append((r.url[:70], (r.post_data or "")[:200]))
            if "trainInfoList" in r.url
            else None,
        )
        try:
            await run_task(page, connection, planner, RAILWAYS_TASK, RAILWAYS_URL)
        except Exception as error:  # noqa: BLE001
            print(f"\n!! run raised: {type(error).__name__}: {error}")
        finally:
            print("\nfinal url:", page.url)
            for name in ("From", "To", "Departure Date"):
                try:
                    value = await page.get_by_role(
                        "textbox", name=name, exact=True
                    ).input_value()
                except Exception as error:  # noqa: BLE001
                    value = f"<{type(error).__name__}>"
                print(f"  {name:15} = {value!r}")

            view = await read_async(page)
            content = view.content
            inferred = [e for e in view.elements if e.inferred]
            print(f"  elements={len(view.elements)} inferred={len(inferred)}")
            print(f"  content: {len(content.tables)} tables, "
                  f"{sum(len(t.rows) for t in content.tables)} rows")
            for table in content.tables[:3]:
                print(f"    headers={table.headers}")
                for row in table.rows[:3]:
                    print("      ", row.cells)
            print("  search requests:", requests)
            print("\n  what the model would see now:")
            print("   " + render_page(view.elements).replace("\n", "\n   ")[:1400])
            await browser.close()

    print(f"\nmodel calls: {planner.calls_made}")
    usage = getattr(provider, "usage", None)
    if usage is not None:
        print("usage:", usage.as_dict() if hasattr(usage, "as_dict") else usage)
    print(f"wall clock: {time.monotonic() - started:.1f}s")


asyncio.run(main())
