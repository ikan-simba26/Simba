"""A password is never in a picture of the page.

Since 2026-10-07 the overlay shows the backend's picture of the real page
behind every step, blurred, and sharp when the person presses "Show the real
page". So every capture paints over password boxes before it leaves the
backend (`loop.send_preview`). Checked on the registration replica's sign-in
page with a password typed in: every pixel inside the box is the mask colour.
The picture is decoded in a browser canvas, because nothing in the project
reads a PNG otherwise and a dependency for one test is not worth adding.
"""

import asyncio
import base64
import concurrent.futures

from playwright.async_api import Page, async_playwright

from backend.orchestrator.loop import MASK_COLOUR, PASSWORD_BOXES, send_preview
from backend.orchestrator.test_asking import ScriptedConnection
from backend.orchestrator.test_orchestrator import REPLICA_URL, replica  # noqa: F401

SECRET = "correct-horse-battery"

#: Every pixel inside a box of a PNG, as "r,g,b" strings.
PIXELS = """async ([data, box]) => {
  const image = new Image();
  image.src = 'data:image/png;base64,' + data;
  await image.decode();
  const canvas = document.createElement('canvas');
  canvas.width = image.width; canvas.height = image.height;
  const context = canvas.getContext('2d');
  context.drawImage(image, 0, 0);
  const d = context.getImageData(box.x, box.y, box.w, box.h).data;
  const seen = new Set();
  for (let i = 0; i < d.length; i += 4) seen.add(`${d[i]},${d[i + 1]},${d[i + 2]}`);
  return [...seen];
}"""


def mask_rgb() -> str:
    value = MASK_COLOUR.lstrip("#")
    return ",".join(str(int(value[i:i + 2], 16)) for i in (0, 2, 4))


async def colours_in_box(page: Page, shot_b64: str, selector: str) -> list[str]:
    box = await page.locator(selector).bounding_box()
    assert box is not None
    # Inside the box, clear of its border and anti-aliased edge.
    inner = {"x": int(box["x"]) + 3, "y": int(box["y"]) + 3,
             "w": int(box["width"]) - 6, "h": int(box["height"]) - 6}
    return await page.evaluate(PIXELS, [shot_b64, inner])


def picture(prepare) -> tuple[list[str], list[str]]:
    """(colours in the box in the preview, colours in the box unmasked)."""

    async def go():
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            try:
                await page.goto(REPLICA_URL)
                selector = await prepare(page)
                connection = ScriptedConnection()
                await send_preview(page, connection, None)
                shot = connection.of("page.preview")[0]["screenshot"]
                plain = base64.b64encode(await page.screenshot()).decode("ascii")
                return (await colours_in_box(page, shot, selector),
                        await colours_in_box(page, plain, selector))
            finally:
                await browser.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, go()).result()


def test_a_typed_password_is_painted_over(replica: str) -> None:  # noqa: F811
    async def prepare(page: Page) -> str:
        await page.fill("#password", SECRET)
        return "#password"

    masked, unmasked = picture(prepare)

    assert masked == [mask_rgb()]
    # The control: without the mask the dots are there to be seen.
    assert len(unmasked) > 1


def test_a_password_shown_as_text_is_painted_over_too(replica: str) -> None:  # noqa: F811
    """A "show password" switch turns the box into an ordinary text box; it is
    still the box for the current password, and still painted over."""
    async def prepare(page: Page) -> str:
        await page.fill("#password", SECRET)
        await page.evaluate("document.getElementById('password').type = 'text'")
        return "#password"

    masked, unmasked = picture(prepare)

    assert masked == [mask_rgb()]
    assert len(unmasked) > 1


def test_an_ordinary_box_is_left_as_it_is(replica: str) -> None:  # noqa: F811
    async def prepare(page: Page) -> str:
        await page.fill("#username", "raham")
        return "#username"

    masked, unmasked = picture(prepare)

    assert masked == unmasked and len(masked) > 1


def test_what_counts_as_a_password_box() -> None:
    assert "input[type=password]" in PASSWORD_BOXES
    assert "current-password" in PASSWORD_BOXES and "new-password" in PASSWORD_BOXES
