"""Serializer tests against the local registration replica."""

from playwright.sync_api import Page

from backend.perception.serializer import Element, serialize

def labels(elements: list[Element]) -> list[str]:
    return [e.label for e in elements]


def find(elements: list[Element], label: str) -> Element:
    matches = [e for e in elements if e.label == label]
    assert len(matches) == 1, f"expected exactly one {label!r}, got {len(matches)}"
    return matches[0]


def test_ids_are_unique_integers_in_order(replica: str, page: Page) -> None:
    page.goto(replica + "/")
    elements = serialize(page)

    assert [e.id for e in elements] == list(range(1, len(elements) + 1))


def test_login_form_controls(replica: str, page: Page) -> None:
    page.goto(replica + "/")
    elements = serialize(page)

    username = find(elements, "Student ID or Username")
    assert (username.role, username.type) == ("textbox", "type")

    password = find(elements, "Password")
    assert (password.role, password.type) == ("textbox", "type")

    sign_in = find(elements, "Sign In")
    assert (sign_in.role, sign_in.type) == ("button", "click")

    remember = find(elements, "Remember this device for 30 days")
    assert (remember.role, remember.type) == ("checkbox", "check")


def test_password_input_is_distinguishable_from_text_input(replica: str, page: Page) -> None:
    """The AX tree alone cannot tell these apart; the DOM enrichment can."""
    page.goto(replica + "/")
    elements = serialize(page)

    username = find(elements, "Student ID or Username")
    password = find(elements, "Password")

    # Identical to the accessibility tree...
    assert username.role == password.role == "textbox"
    assert username.tag == password.tag == "input"

    # ...and separable only by the DOM type attribute.
    assert username.input_type == "text"
    assert password.input_type == "password"
    assert password.is_password
    assert not username.is_password


def test_tag_and_input_type_are_captured(replica: str, page: Page) -> None:
    page.goto(replica + "/")
    elements = serialize(page)

    sign_in = find(elements, "Sign In")
    assert (sign_in.tag, sign_in.input_type) == ("button", "submit")

    remember = find(elements, "Remember this device for 30 days")
    assert (remember.tag, remember.input_type) == ("input", "checkbox")

    home = find(elements, "Home")
    assert (home.tag, home.input_type) == ("a", None)


def test_labels_come_from_the_accessibility_tree(replica: str, page: Page) -> None:
    """The username input has no inline text; its name comes from <label for>."""
    page.goto(replica + "/")
    elements = serialize(page)

    assert "Student ID or Username" in labels(elements)


def test_nav_links_are_serialized(replica: str, page: Page) -> None:
    page.goto(replica + "/")
    elements = serialize(page)

    links = [e for e in elements if e.role == "link"]
    assert len(links) > 20
    assert all(e.type == "click" for e in links)
    assert "Academic Calendar" in labels(elements)


def test_course_table_register_buttons(replica: str, page: Page) -> None:
    _log_in(page, replica)
    elements = serialize(page)

    register = [e for e in elements if e.label.startswith("Register for ")]
    assert len(register) == 20
    assert "Register for CS-401" in labels(elements)
    assert all(e.role == "button" and e.type == "click" for e in register)


def test_dismissed_modal_drops_out_of_the_serialization(replica: str, page: Page) -> None:
    """Hidden elements are absent from the AX tree, unlike in raw HTML."""
    _log_in(page, replica)
    assert "Close" in labels(serialize(page))

    page.click("#modal-close")

    assert "Close" not in labels(serialize(page))


def _log_in(page: Page, replica: str) -> None:
    page.goto(replica + "/")
    page.fill("#username", "raham")
    page.fill("#password", "hunter2")
    page.click("button[type=submit]")
    page.wait_for_url(replica + "/courses")


# --- a password field's value never enters perception -------------------------


def test_a_typed_password_is_never_read_into_the_page(replica: str, page: Page) -> None:
    """CDP's snapshot reads every input's live value, a password field's
    included. Until 2026-10-03 a typed password sat in `Element.value` and in
    the document's `input_values`; nothing sent it on, but every reader of a
    value was one line from leaking it. Now a password field reads as a fixed
    mask, and the text field beside it still reads what it holds."""
    from backend.perception.snapshot import SECRET_MASK
    from backend.perception.serializer import read

    secret = "S3cret-perception-probe!"
    page.goto(replica)
    page.fill("#username", "raham")
    page.fill("#password", secret)

    view = read(page)

    password = next(e for e in view.elements if e.is_password)
    username = next(e for e in view.elements if e.label == "Student ID or Username")
    assert password.value == SECRET_MASK
    assert username.value == "raham"
    assert secret not in repr(view.elements)
    assert all(secret not in v for v in view.document.input_values.values())


def test_an_empty_password_field_reads_empty(replica: str, page: Page) -> None:
    """Filled or not is still visible: the mask means something is there."""
    from backend.perception.serializer import read

    page.goto(replica)
    password = next(e for e in read(page).elements if e.is_password)

    assert password.value == ""
