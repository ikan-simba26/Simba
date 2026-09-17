"""Drive one hardcoded railways run against the live site and print the flow.

Produced: EVALUATION.md 2026-09-08 "the live flow completes" (5/5, 46.1s),
and the 54s re-verification STATUS.md cites for 2026-09-09. **Live site**:
one full read-only search. No model.

Moved from `.scratch/rail_run.py` on 2026-09-17, unchanged but for paths.

Run from the repo root: `python -m tools.evaluation.railways_hardcoded_run`.
"""
import asyncio, io, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.async_api import async_playwright
from backend.orchestrator.loop import Connection, run_task
from backend.orchestrator.plan import HardcodedPlanner
from backend.orchestrator.railways_plan import RAILWAYS_PLAN, RAILWAYS_TASK, RAILWAYS_URL
from backend.perception.serializer import read_async

UA = ("SIMBA-screener/0.1 (final-year university project; read-only; "
      "+https://github.com/ikan-simba26/Simba)")

class Printing(Connection):
    def __init__(self): self.seq = 0; self.sent = []
    async def send(self, message_type, payload):
        self.seq += 1
        d = payload.model_dump()
        self.sent.append((message_type, d))
        if message_type == "step.presented":
            print(f"[{self.seq:2}] step {d['step_index']}/{d['step_total']}: {d['instruction']}")
        elif message_type == "state.changed":
            pass
        elif message_type == "page.preview":
            print(f"[{self.seq:2}] page.preview  caption={d['caption']!r}")
        else:
            print(f"[{self.seq:2}] {message_type}: {d}")
    async def receive(self, message_type, step_index=None, on_other=None):
        return {"type": "step.response",
                "payload": {"step_index": step_index, "action_id": "confirm", "input_values": {}}}

async def main():
    c = Printing(); started = time.monotonic()
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        ctx = await b.new_context(user_agent=UA, viewport={"width":1280,"height":800})
        page = await ctx.new_page()
        seen = []
        page.on("request", lambda r: seen.append((r.url[:70], (r.post_data or "")[:200]))
                if "trainInfoList" in r.url else None)
        try:
            await run_task(page, c, HardcodedPlanner(RAILWAYS_PLAN), RAILWAYS_TASK, RAILWAYS_URL)
        finally:
            print("\nfinal url:", page.url)
            for n in ("From","To","Departure Date"):
                try:
                    v = await page.get_by_role("textbox", name=n, exact=True).input_value()
                except Exception as e:
                    v = f"<{type(e).__name__}>"
                print(f"  {n:15} = {v!r}")
            view = await read_async(page)
            cc = view.content
            print(f"  elements={len(view.elements)} inferred={sum(1 for e in view.elements if e.inferred)}")
            print(f"  content: {len(cc.headings)} headings, {len(cc.tables)} tables, "
                  f"{sum(len(t.rows) for t in cc.tables)} rows, {len(cc.pairs)} pairs")
            print("  search requests:", seen)
            for i, t in enumerate(cc.tables):
                print(f"  table[{i}] headers={t.headers} rows={len(t.rows)}")
                for r in t.rows[:4]:
                    print("      ", r.cells)
            print("  says LAHORE CANTT:", cc.says("LAHORE CANTT"))
            print("  prominent:", [(v.text[:40], v.font_size) for v in cc.values][:6])
            await b.close()
    print(f"wall clock: {time.monotonic() - started:.1f}s")

asyncio.run(main())
