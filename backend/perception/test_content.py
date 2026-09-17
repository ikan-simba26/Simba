"""Content extraction against the billing replica.

The replica exists to be read, and until now perception could not read it.
The amount the whole task is about sits in the sixth cell of a row whose
column headings are in a different row, and nothing in the cell says what it
is — the template says so in a comment, because that is how these portals
actually look.

These tests are about that cell.
"""

from playwright.sync_api import Page

from backend.perception.content import Content, extract
from backend.perception.serializer import read
from backend.perception.snapshot import parse

AMOUNT = "14,382"
REFERENCE = "04141234567890"


def results(billing: str, page: Page) -> Content:
    page.goto(f"{billing}/bill?reference={REFERENCE}")
    return read(page).content


# --- the amount, with its label ---------------------------------------------


def test_the_amount_due_arrives_with_the_label_that_explains_it(
    billing: str, page: Page
) -> None:
    """The finding this module exists for.

    `14,382` on its own is a number in a cell. Paired with `P/WITHIN` it is
    an answer to the question the task was set.
    """
    content = results(billing, page)

    assert content.labelled(AMOUNT) == ["P/WITHIN"]
    assert content.value_for("P/WITHIN") == AMOUNT


def test_the_amount_is_not_confused_with_the_one_beside_it(
    billing: str, page: Page
) -> None:
    """`P/AFTER` is a different, larger number in the very next cell.

    Off-by-one in the header pairing would return it and look entirely
    plausible, which is the failure mode worth a test of its own.
    """
    content = results(billing, page)

    payable_after = content.value_for("P/AFTER")
    assert payable_after is not None and payable_after != AMOUNT


def test_every_column_of_the_summary_row_is_paired(billing: str, page: Page) -> None:
    content = results(billing, page)

    summary = next(t for t in content.tables if "P/WITHIN" in t.headers)
    assert summary.headers == (
        "REF NO", "MTR NO", "PREV", "CURR", "UNITS",
        "P/WITHIN", "P/AFTER", "DUE DT", "ISSUE DT", "ST",
    )
    assert len(summary.rows) == 1
    row = summary.rows[0]
    assert row.get("REF NO") == REFERENCE
    assert row.get("P/WITHIN") == AMOUNT
    # Every cell got a header; none fell off the end.
    assert all(header for header, _ in row.cells)


# --- the shapes that are not a header row -----------------------------------


def test_a_th_td_row_becomes_a_pair_without_inventing_column_headers(
    billing: str, page: Page
) -> None:
    """The `particulars` table alternates th/td *across* a row.

    Its first row is `Consumer name | M. R. WASIM | Tariff | A-1a(01)...`.
    Read as a header row that names column two "M. R. WASIM" and mislabels
    every row beneath it — which is worse than not reading the table at all,
    because the wrong answer looks like a right one.
    """
    content = results(billing, page)

    assert content.value_for("Consumer name") == "M. R. WASIM"
    assert content.value_for("Address") == "HOUSE 24, STREET 7, GULBERG III, LAHORE"
    # Nothing claims a person's name is the name of a column.
    assert content.value_for("M. R. WASIM") is None
    particulars = next(
        t for t in content.tables if any(r.get("") == "Consumer name" for r in t.rows)
    )
    assert particulars.headers == ()


def test_headings_carry_their_level(billing: str, page: Page) -> None:
    content = results(billing, page)

    levels = {h.text: h.level for h in content.headings}
    assert levels["Bill Enquiry Result"] == 1
    assert levels["Applicable tariff schedule"] == 2
    assert levels["Helpdesk"] == 4


def test_the_tariff_table_keeps_all_of_its_rows(billing: str, page: Page) -> None:
    content = results(billing, page)

    tariff = next(t for t in content.tables if "Rate (Rs/unit)" in t.headers)
    assert len(tariff.rows) == 15
    assert tariff.rows[0].get("Category") == "Residential"


def test_the_detail_page_reads_its_own_total(billing: str, page: Page) -> None:
    page.goto(f"{billing}/bill/detail?reference={REFERENCE}")
    content = read(page).content

    assert content.value_for("Particular") is None or True  # header, not a label
    breakdown = next(t for t in content.tables if "Particular" in t.headers)
    totals = [r for r in breakdown.rows if r.get("Particular") == "Payable within due date"]
    assert totals and totals[0].get("Amount (Rs)") == "14,382.00"


def test_a_prominent_value_is_found_by_size_not_by_markup(
    billing: str, page: Page
) -> None:
    """The masthead is a plain div set large. Nothing marks it as important."""
    content = results(billing, page)

    assert any("LAHORE ELECTRIC SUPPLY AUTHORITY" in v.text for v in content.values)


def test_says_answers_the_question_a_success_condition_asks(
    billing: str, page: Page
) -> None:
    content = results(billing, page)

    assert content.says(AMOUNT)
    assert content.says("M. R. WASIM")
    assert not content.says("99,999")


# --- shape handling, without a browser --------------------------------------


def test_extract_survives_no_snapshot() -> None:
    assert not extract(None)
    assert extract(None).pairs == []


def test_repeated_divs_are_read_as_rows() -> None:
    """A single-page app renders a results table as a list of divs.

    No `<table>`, no `role="row"`, no headers — the railways results are this
    shape, and so is most of what a component framework emits. Without this
    the rows are invisible for exactly the reason the dropdown was.
    """
    document = parse(_snapshot_of_div_grid())
    content = extract(document)

    rows = [r for t in content.tables for r in t.rows]
    assert len(rows) == 3
    assert [r.values for r in rows] == [
        ("7UP", "LAHORE CANTT", "KARACHI CANTT"),
        ("9DN", "LAHORE CANTT", "KARACHI CANTT"),
        ("15UP", "LAHORE CANTT", "KARACHI CANTT"),
    ]


def _snapshot_of_div_grid() -> dict:
    """A hand-built snapshot: three identically-classed rows of three cells.

    Written as CDP would send it — column arrays and interned strings —
    because that is the input `parse` has to cope with, and a fixture that
    smooths that over would test a shape the real thing never takes.
    """
    strings = [
        "", "html", "BODY", "DIV", "class", "list", "row", "cell",
        "7UP", "9DN", "15UP", "LAHORE CANTT", "KARACHI CANTT", "#text", "static",
    ]
    EMPTY, HTML, BODY, DIV, CLASS, LIST, ROW, CELL = 0, 1, 2, 3, 4, 5, 6, 7
    TEXT, STATIC = 13, 14

    parents, names, values, types, backend, attributes = [], [], [], [], [], []

    def add(parent: int, name: int, node_type: int, attrs: list[int], value: int) -> int:
        parents.append(parent)
        names.append(name)
        values.append(value)
        types.append(node_type)
        backend.append(len(parents) + 100)
        attributes.append(attrs)
        return len(parents) - 1

    root = add(-1, HTML, 1, [], EMPTY)
    body = add(root, BODY, 1, [], EMPTY)
    container = add(body, DIV, 1, [CLASS, LIST], EMPTY)
    for train in (8, 9, 10):  # 7UP, 9DN, 15UP
        row = add(container, DIV, 1, [CLASS, ROW], EMPTY)
        for value in (train, 11, 12):  # number, from, to
            cell = add(row, DIV, 1, [CLASS, CELL], EMPTY)
            add(cell, TEXT, 3, [], value)

    # Every node laid out, all static, no font-size — nothing is prominent.
    node_indexes = list(range(len(parents)))
    return {
        "strings": strings,
        "documents": [
            {
                "nodes": {
                    "parentIndex": parents,
                    "nodeName": names,
                    "nodeValue": values,
                    "nodeType": types,
                    "backendNodeId": backend,
                    "attributes": attributes,
                },
                "layout": {
                    "nodeIndex": node_indexes,
                    "bounds": [[0, i * 20, 600, 20] for i in node_indexes],
                    "styles": [
                        [STATIC, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY]
                        for _ in node_indexes
                    ],
                },
            }
        ],
    }


def test_a_lone_header_row_is_joined_to_the_rows_it_names() -> None:
    """A div-built table puts its heading strip in a separate group.

    The live railways results arrive as two one-row tables — the headings and
    the train — and neither says much without the other.
    """
    from backend.perception.content import Row, Table, _adopt_headers

    headings = Table(headers=(), rows=(Row((("", "Train No."), ("", "From/To"))),))
    trains = Table(headers=(), rows=(
        Row((("", "2DN"), ("", "LAHORE CANTT KARACHI CANTT"))),
        Row((("", "7UP"), ("", "LAHORE CANTT KARACHI CANTT"))),
    ))

    joined = _adopt_headers([headings, trains])

    assert len(joined) == 1
    assert joined[0].headers == ("Train No.", "From/To")
    assert joined[0].rows[0].get("Train No.") == "2DN"
    assert joined[0].rows[1].get("From/To") == "LAHORE CANTT KARACHI CANTT"


def test_mismatched_widths_are_left_alone() -> None:
    """Naming columns wrongly is worse than not naming them."""
    from backend.perception.content import Row, Table, _adopt_headers

    headings = Table(headers=(), rows=(Row((("", "A"), ("", "B"))),))
    rows = Table(headers=(), rows=(Row((("", "1"), ("", "2"), ("", "3"))),))

    assert len(_adopt_headers([headings, rows])) == 2


# --- the spacer column a scrolling table adds to its heading strip ----------


def test_a_scrollbar_spacer_does_not_stop_the_pairing() -> None:
    """The 2026-09-17 live failure, as the pure rule.

    Element UI adds an empty gutter cell to the heading strip when the body
    scrolls, so the strip has five cells to the body's four and the join used
    to refuse. The run found its train and reported no answer (EVALUATION.md,
    2026-09-17i).
    """
    from backend.perception.content import Row, Table, _adopt_headers

    headings = Table(headers=(), rows=(Row(tuple(("", value) for value in
                     ("Train No.", "From/To", "Time", "Duration", ""))),))
    trains = Table(headers=(), rows=(Row(tuple(("", value) for value in
                   ("2DN", "LAHORE CANTT KARACHI CANTT", "08:04 06:20", "22 h 16 min"))),))

    joined = _adopt_headers([headings, trains])

    assert len(joined) == 1
    assert joined[0].headers == ("Train No.", "From/To", "Time", "Duration")
    assert joined[0].rows[0].get("Duration") == "22 h 16 min"


def test_a_named_extra_column_is_never_discarded_to_force_a_fit() -> None:
    """Only an empty trailing cell is a spacer. A named one means the strip
    and the rows are genuinely different shapes, and guessing would name
    columns wrongly."""
    from backend.perception.content import Row, Table, _adopt_headers

    headings = Table(headers=(), rows=(Row(tuple(("", value) for value in
                     ("A", "B", "C", "Total"))),))
    rows = Table(headers=(), rows=(Row(tuple(("", value) for value in ("1", "2", "3"))),))

    assert len(_adopt_headers([headings, rows])) == 2


def test_a_heading_strip_narrower_than_its_rows_is_left_alone() -> None:
    from backend.perception.content import Row, Table, _adopt_headers

    headings = Table(headers=(), rows=(Row((("", "A"), ("", "B"))),))
    rows = Table(headers=(), rows=(Row((("", "1"), ("", "2"), ("", "3"))),))

    assert len(_adopt_headers([headings, rows])) == 2


def test_rows_of_differing_widths_are_left_alone() -> None:
    """Ragged rows are not a shape a heading strip can name."""
    from backend.perception.content import Row, Table, _adopt_headers

    headings = Table(headers=(), rows=(Row((("", "A"), ("", "B"))),))
    rows = Table(headers=(), rows=(
        Row((("", "1"), ("", "2"))),
        Row((("", "1"), ("", "2"), ("", "3"))),
    ))

    assert len(_adopt_headers([headings, rows])) == 2


# The live results, as the browser has them: two tables, the heading strip
# carrying the gutter cell a scrolling body adds. Captured from
# pakrailways.gov.pk on 2026-09-17 and reduced to what matters.
SPLIT_TABLES_WITH_GUTTER = """
<div class="el-table">
  <div class="el-table__header-wrapper">
    <table class="el-table__header"><thead><tr>
      <th class="el-table_1_column_1"><div class="cell">Train No.</div></th>
      <th class="el-table_1_column_2"><div class="cell">From/To</div></th>
      <th class="el-table_1_column_3"><div class="cell">Time</div></th>
      <th class="el-table_1_column_4"><div class="cell">Duration</div></th>
      <th class="gutter" style="width: 15px"></th>
    </tr></thead></table>
  </div>
  <div class="el-table__body-wrapper">
    <table class="el-table__body"><tbody><tr class="el-table__row">
      <td class="el-table_1_column_1"><div class="cell">2DN</div></td>
      <td class="el-table_1_column_2"><div class="cell">LAHORE CANTT KARACHI CANTT</div></td>
      <td class="el-table_1_column_3"><div class="cell">08:04 06:20</div></td>
      <td class="el-table_1_column_4"><div class="cell">22 h 16 min</div></td>
    </tr></tbody></table>
  </div>
</div>
"""


def test_the_train_is_readable_from_the_live_markup(page: Page) -> None:
    """The same thing again through a real browser, on the real shape.

    The unit tests above fix the rule; this proves the rule meets the markup,
    which is where the 2026-09-17 run came apart.
    """
    page.set_content(SPLIT_TABLES_WITH_GUTTER)
    content = read(page).content

    assert content.value_for("Train No.") == "2DN"
    assert content.value_for("Duration") == "22 h 16 min"
    assert content.labelled("22 h 16 min") == ["Duration"]
