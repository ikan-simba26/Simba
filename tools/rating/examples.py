"""The two worked examples raters see before the first picture.

    python -m tools.rating.examples          # photographs both, once

One calm page and one cluttered page, **neither of them among the 50**, each
shown with the answer it would get and one short sentence why, so a rater
knows what the two ends of "How overwhelming does this page feel?" look like
before rating anything (DECISIONS.md, *Two sets of 30*). The calm one is
answered "Not at all" and the cluttered one "Very", not "Extremely", so the
top answer is left for the rater to place.

Photographed the way the 50 are (`capture.photograph`: headless, 1280x800,
scrollbars hidden), read-only. The pictures go to `data/rating/examples/`,
which is not committed, like the 50; `data/rating/examples.json`, which is,
records their hashes, and `read` refuses a picture that is not the one
recorded. Taken once: the sentences describe these exact pictures, so a
recapture means reading the sentences against the new pictures again.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from tools.evaluation.collect_corpus import UA
from tools.rating.capture import VIEWPORT, new_run, photograph

REPO = Path(__file__).resolve().parents[2]
FOLDER = REPO / "data" / "rating" / "examples"
RECORD = REPO / "data" / "rating" / "examples.json"


async def turn_down_cookies(page) -> None:
    """GOV.UK's cookie banner covers a third of the calm page; rejecting the
    additional cookies, then hiding the message that says so, removes it and
    changes nothing but a cookie."""
    await page.get_by_role("button", name="Reject additional cookies").first.click()
    await page.wait_for_timeout(500)
    await page.get_by_role("button", name="Hide cookie message").first.click()
    await page.wait_for_timeout(800)


#: `answer` is a point of the scale, 1 to 5 (`serve.LABELS`). `says` is the
#: one sentence shown under the picture, before the answer: it describes the
#: picture as it was taken (2026-10-23), so it is checked against the picture.
#: Chosen with nothing in the news in them; CNN's front page was tried first
#: for the cluttered one and was full of politics.
EXAMPLES: list[dict] = [
    {"name": "E1", "url": "https://www.gov.uk/bank-holidays", "drive": turn_down_cookies,
     "answer": 1, "says": "One clear heading, a few links and plenty of space."},
    {"name": "E2", "url": "https://www.newegg.com/", "drive": None,
     "answer": 4, "says": "A pop-up covers a crowded shop page full of menus and offers."},
]


class ExamplesMissing(Exception):
    """The example pictures are not on disk as recorded, and why."""


def read(record: Path = RECORD, folder: Path = FOLDER) -> list[dict]:
    """The examples, in order, each with its picture's path, checked against
    the hash recorded when it was taken."""
    if not record.exists():
        raise ExamplesMissing(f"{record} is missing; run python -m tools.rating.examples")
    rows = json.loads(record.read_text(encoding="utf-8"))["examples"]
    for row in rows:
        file = folder / row["file"]
        if not file.exists():
            raise ExamplesMissing(f"{file} is missing; run python -m tools.rating.examples")
        if hashlib.sha256(file.read_bytes()).hexdigest() != row["sha256"]:
            raise ExamplesMissing(f"{file} is not the picture {record.name} recorded")
        row["path"] = str(file)
    return rows


async def take(folder: Path = FOLDER) -> list[dict]:
    folder.mkdir(parents=True, exist_ok=True)
    run = new_run()
    rows = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=["--hide-scrollbars"])
        context = await browser.new_context(user_agent=UA, viewport=VIEWPORT,
                                            device_scale_factor=1, bypass_csp=True)
        page = await context.new_page()
        for example in EXAMPLES:
            row, _ = await photograph(page, example["url"], example["drive"], "example", run,
                                      into=folder)
            if "error" in row:
                raise ExamplesMissing(f"{example['url']}: {row['error']}")
            final = folder / f"{example['name']}.png"
            (folder / row["file"]).replace(final)
            rows.append({**{k: v for k, v in example.items() if k != "drive"},
                         "state": row["state"], "file": final.name, "sha256": row["sha256"],
                         "title": row["title"], "layout_width": row["layout_width"],
                         "captured_at": row["captured_at"]})
        await browser.close()
    return rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = asyncio.run(take())
    RECORD.write_text(json.dumps({"made_by": "python -m tools.rating.examples",
                                  "viewport": VIEWPORT, "examples": rows},
                                 indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for row in rows:
        print(f"{row['file']}: {row['url']} ({row['title']}, layout {row['layout_width']}px)")
    print(f"recorded in {RECORD.relative_to(REPO)}")


if __name__ == "__main__":
    main()
