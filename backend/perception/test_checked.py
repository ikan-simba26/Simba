"""A ticked box is not the same page as an unticked one (2026-11-14).

A checkbox's value used to be its `value` attribute ("on"), whether ticked or
not, so ticking one changed nothing the loop compares: the AI planner's tick of
"I agree to the Terms and Conditions" was judged a failure, tried again — which
unticked it — and the form went in without it (EVALUATION.md, 2026-11-14b).
"""

from playwright.sync_api import Page

from backend.perception.serializer import read

FORM = """<input type="checkbox" id="terms"><label for="terms">I agree to the Terms</label>
<input type="radio" name="size" id="s"><label for="s">Small</label>
<input type="radio" name="size" id="l" checked><label for="l">Large</label>
<label for="n">Name</label> <input id="n" value="Ayesha">"""


def values(page: Page) -> dict[str, str]:
    return {e.label: e.value for e in read(page).elements}


def test_a_box_reads_ticked_or_not(page: Page) -> None:
    page.set_content(FORM)
    before = values(page)
    assert before["I agree to the Terms"] == ""
    assert before["Small"] == "" and before["Large"] == "checked"
    assert before["Name"] == "Ayesha"          # a text box keeps what it holds

    page.locator("#terms").check()
    page.locator("#s").check()
    after = values(page)
    assert after["I agree to the Terms"] == "checked"
    assert after["Small"] == "checked" and after["Large"] == ""
