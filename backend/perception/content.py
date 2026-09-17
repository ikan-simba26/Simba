"""The second output channel: what the page *says*, not what it offers.

Perception has only ever returned interactive elements, and that turns out to
be half a page. Two consequences, both recorded before this module existed:

  * The billing replica's whole goal is to read an amount. The amount lives
    in the sixth cell of a table row, the column headings are in a different
    row, and nothing in the cell says what it is. No step could assert the
    amount was found, so `BILLING_TASK.success` checks that the right *page*
    was reached instead — a proxy for the goal, and openly labelled as one.
  * The railways search has `success=None` outright. Its results are a table
    of static text in a single-page app: the URL does not change, the title
    does not change, no row is interactive. There was nothing to assert
    against at all.

Both are the same missing channel. This module adds it, reading the same
DOMSnapshot the other two readers already use — no extra round trip.

Four shapes, because four shapes cover what a form-and-table portal actually
puts on a page:

  * **Headings**, with their level, so a planner can tell where it is.
  * **Tables**, with every row's cells paired to the column header above
    them. This is the one that solves the sixth-cell problem: `14,382` on its
    own is a number, and `("P/WITHIN", "14,382")` is an answer.
  * **Label/value pairs**, from definition lists, from `th`/`td` rows, and
    from the flattened table rows above.
  * **Prominent standalone values** — text set noticeably larger than the
    page's own baseline. A portal that wants you to see one number makes it
    big, and that is a signal available from computed styles for free.

Nothing here is interactive and nothing here gets an element id. Content is a
separate channel precisely so a planner cannot confuse "the page says 14,382"
with "there is a button called 14,382".
"""

from dataclasses import dataclass, field
from statistics import median

from backend.perception.snapshot import Document, visible

HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
CELL_TAGS = {"td", "th"}
HEADER_ROLES = {"columnheader", "rowheader"}
CELL_ROLES = {"cell", "gridcell", *HEADER_ROLES}

# How much larger than the page's own median text a value has to be set before
# it reads as deliberately prominent. Relative, not absolute, because a portal
# with 11px body text and a portal with 16px body text both have a "big
# number" and it is not the same number of pixels.
PROMINENCE_RATIO = 1.45
# Prominent *values* are short. A large paragraph is a large paragraph.
MAX_VALUE_CHARS = 40
# Repeated sibling records need at least this many to read as a list of rows.
MIN_RECORDS = 2

# A panel stacked out of flow above the page is transient UI, not content.
# Same test the other two snapshot readers use, so all three agree on what a
# floating panel is.
FLOATING_POSITIONS = {"absolute", "fixed"}
MIN_FLOAT_LEVEL = 5


@dataclass(frozen=True)
class Heading:
    level: int
    text: str


@dataclass(frozen=True)
class Row:
    """One row, already paired against the column headers above it.

    `cells` is ordered, so a row still reads left to right, and it is pairs,
    so no caller has to count columns to find out what a value means.
    """

    cells: tuple[tuple[str, str], ...]

    def get(self, header: str) -> str | None:
        for name, value in self.cells:
            if name == header:
                return value
        return None

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(value for _, value in self.cells)


@dataclass(frozen=True)
class Table:
    headers: tuple[str, ...]
    rows: tuple[Row, ...]
    caption: str = ""


@dataclass(frozen=True)
class Pair:
    label: str
    value: str


@dataclass(frozen=True)
class Value:
    """A short piece of text the page has set noticeably larger than its own."""

    text: str
    font_size: float


@dataclass
class Content:
    headings: list[Heading] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    pairs: list[Pair] = field(default_factory=list)
    values: list[Value] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.headings or self.tables or self.pairs or self.values)

    def labelled(self, value: str) -> list[str]:
        """Every label this page attaches to a value. The lookup answer."""
        return [pair.label for pair in self.pairs if pair.value == value]

    def value_for(self, label: str) -> str | None:
        for pair in self.pairs:
            if pair.label == label:
                return pair.value
        return None

    def says(self, text: str) -> bool:
        """Whether the text appears anywhere in the readable content.

        The blunt instrument, for a success condition that only needs to know
        the page mentions something at all.
        """
        text = text.strip()
        if not text:
            return False
        haystacks = [h.text for h in self.headings]
        haystacks += [v.text for v in self.values]
        for pair in self.pairs:
            haystacks += [pair.label, pair.value]
        for table in self.tables:
            haystacks += list(table.headers)
            for row in table.rows:
                haystacks += list(row.values)
        return any(text in h for h in haystacks)


def extract(document: Document | None) -> Content:
    """Read a page's readable content out of a parsed DOMSnapshot. Pure."""
    if document is None:
        return Content()

    transient = _transient(document)
    content = Content()
    content.headings = _headings(document, transient)
    content.tables = _adopt_headers(
        _tables(document, transient) + _record_lists(document, transient)
    )
    content.pairs = _pairs(document, content.tables, transient)
    content.values = _prominent(document, transient)
    return content


def _without_gutter(headers: tuple[str, ...], width: int) -> tuple[str, ...] | None:
    """`headers` cut to `width`, or None if they cannot be.

    A component library that scrolls a table's body adds a spacer column to
    the heading strip, the width of the scrollbar, with no text in it —
    Element UI calls it a gutter. The strip then has one cell more than every
    row beneath it.

    That is state, not markup: the same page pairs correctly when the body
    does not scroll. On 2026-09-17 a live railways run searched, found its
    train, and reported no answer at all, because the results heading strip
    had five cells to the body's four and the join below refused (EVALUATION.md,
    2026-09-17i). Only *empty* trailing cells are dropped, and only as many as
    the mismatch needs, so a real column is never discarded to force a fit.
    """
    if len(headers) == width:
        return headers
    if len(headers) < width:
        return None
    if any(cell.strip() for cell in headers[width:]):
        return None
    return headers[:width]


def _adopt_headers(tables: list[Table]) -> list[Table]:
    """Join a lone header row to the rows it names.

    A framework that builds a table out of `div`s builds the heading strip out
    of `div`s too, and it is a different group of them — a different class, a
    different parent — so it arrives here as a separate one-row table. The
    live railways results come out exactly like that: `Train No. | From/To |
    Time | Duration` in one, `2DN | LAHORE CANTT KARACHI CANTT | 08:04 06:20 |
    22 h 16 min` in the next, and neither means much without the other.

    Joined only when the widths match, once any empty trailing spacer cell is
    discounted (`_without_gutter`). A mismatch that is not a spacer leaves
    both alone rather than naming columns wrongly.
    """
    joined: list[Table] = []
    index = 0
    while index < len(tables):
        table = tables[index]
        following = tables[index + 1] if index + 1 < len(tables) else None
        widths = {len(row.cells) for row in following.rows} if following else set()
        headers = (
            _without_gutter(table.rows[0].values, widths.pop())
            if following is not None
            and not table.headers
            and not following.headers
            and len(table.rows) == 1
            and following.rows
            and len(widths) == 1
            else None
        )
        if headers is not None:
            joined.append(
                Table(
                    headers=headers,
                    rows=tuple(
                        Row(cells=tuple(zip(headers, row.values)))
                        for row in following.rows
                    ),
                    caption=following.caption,
                )
            )
            index += 2
            continue
        joined.append(table)
        index += 1
    return joined


def _transient(document: Document) -> set[int]:
    """Everything inside a floating panel — a picker, a dropdown, a menu.

    These are controls, and they already reach a planner through the
    interactive channel. Read as *content* they are worse than noise: the
    live railways date picker is a properly built `<table>` with `Sun`..`Sat`
    headers and six rows of days, so "the page has at least one row of
    results" was satisfied by opening a calendar. A success condition that a
    date picker can satisfy is not a success condition.

    The cost is that content genuinely inside a modal is skipped too. That is
    a real limitation and it is recorded in STATUS.md rather than guessed at
    here — a modal's content is also blocking content, and the loop's job
    with one of those is to dismiss it.
    """
    floating: set[int] = set()
    for node_index, style in document.styles.items():
        if style.get("position") not in FLOATING_POSITIONS:
            continue
        try:
            level = int(style.get("z-index") or "")
        except ValueError:
            continue
        if level >= MIN_FLOAT_LEVEL:
            floating |= document.subtree(node_index)
    return floating


# --- headings ---------------------------------------------------------------


def _headings(document: Document, transient: set[int]) -> list[Heading]:
    headings: list[Heading] = []
    for node_index in range(len(document)):
        if not document.is_element(node_index):
            continue
        if not _shown(document, node_index, transient):
            continue

        tag = document.tag(node_index)
        level = HEADING_TAGS.get(tag)
        if level is None and document.attribute(node_index, "role") == "heading":
            try:
                level = int(document.attribute(node_index, "aria-level") or 2)
            except ValueError:
                level = 2
        if level is None:
            continue

        text = document.text_of(node_index, limit=200)
        if text:
            headings.append(Heading(level=level, text=text))
    return headings


# --- tables -----------------------------------------------------------------


def _tables(document: Document, transient: set[int]) -> list[Table]:
    """Real `<table>` markup, and ARIA grids built out of `div`s."""
    tables: list[Table] = []
    for node_index in range(len(document)):
        if not document.is_element(node_index):
            continue
        tag = document.tag(node_index)
        role = document.attribute(node_index, "role")
        if tag != "table" and role not in {"table", "grid"}:
            continue
        if not _shown(document, node_index, transient):
            continue

        rows = _rows_under(document, node_index)
        if not rows:
            continue

        headers, body = _split_header(rows)
        caption = ""
        for child in document.subtree(node_index):
            if document.tag(child) == "caption":
                caption = document.text_of(child, limit=200)
                break

        built = [_pair_row(headers, cells) for cells in body]
        tables.append(
            Table(headers=tuple(headers), rows=tuple(built), caption=caption)
        )
    return tables


def _rows_under(document: Document, table_index: int) -> list[list[tuple[bool, str]]]:
    """Every row as (is_header_cell, text), in order, nested tables excluded."""
    rows: list[list[tuple[bool, str]]] = []
    for node_index in sorted(document.subtree(table_index)):
        if node_index == table_index or not document.is_element(node_index):
            continue
        tag = document.tag(node_index)
        role = document.attribute(node_index, "role")
        if tag != "tr" and role != "row":
            continue
        # A row belonging to a table nested inside this one is that table's.
        if _nearest_table(document, node_index) != table_index:
            continue
        if not _shown(document, node_index):
            continue

        cells: list[tuple[bool, str]] = []
        for child in document.children.get(node_index, ()):
            if not document.is_element(child):
                continue
            child_tag = document.tag(child)
            child_role = document.attribute(child, "role")
            if child_tag in CELL_TAGS or child_role in CELL_ROLES:
                is_header = child_tag == "th" or child_role in HEADER_ROLES
                cells.append((is_header, document.text_of(child, limit=200)))
        if cells:
            rows.append(cells)
    return rows


def _nearest_table(document: Document, node_index: int) -> int:
    for ancestor in document.ancestors(node_index):
        if document.tag(ancestor) == "table":
            return ancestor
        if document.attribute(ancestor, "role") in {"table", "grid"}:
            return ancestor
    return -1


def _split_header(
    rows: list[list[tuple[bool, str]]]
) -> tuple[list[str], list[list[tuple[bool, str]]]]:
    """Decide which row names the columns, if any.

    A row only names the columns if *every* cell in it is a header cell. The
    billing replica's `particulars` table alternates `th`/`td` across a single
    row — `Consumer name | M. R. WASIM | Tariff | A-1a(01)` — so it has no
    header row at all; each row is its own sequence of label/value pairs and
    `_header_cell_pairs` reads it that way. Going on cell count alone would
    name the second column "M. R. WASIM" and mislabel every row under it,
    which is worse than not reading the table, because it looks like an answer.
    """
    if not rows:
        return [], []
    first, rest = rows[0], rows[1:]
    if rest and all(is_header and text for is_header, text in first):
        return [text for _, text in first], rest
    return [], rows


def _pair_row(headers: list[str], cells: list[tuple[bool, str]]) -> Row:
    paired: list[tuple[str, str]] = []
    for position, (_, cell) in enumerate(cells):
        header = headers[position] if position < len(headers) else ""
        paired.append((header, cell))
    return Row(cells=tuple(paired))


def _record_lists(document: Document, transient: set[int]) -> list[Table]:
    """Rows built from repeated `div`s, which is how a SPA renders a table.

    A framework that renders results as a list of identically-classed
    containers has a table in every sense except the tag. Without this the
    railways results — the whole point of the search — are invisible for
    exactly the reason the dropdown was.
    """
    groups: dict[tuple[int, str, str], list[int]] = {}
    for node_index in range(len(document)):
        if not document.is_element(node_index):
            continue
        tag = document.tag(node_index)
        if tag in {"tr", "option", "script", "style"}:
            continue
        parent = document.parents[node_index]
        classes = document.attribute(node_index, "class").strip()
        if parent < 0 or not classes or node_index in transient:
            continue
        groups.setdefault((parent, tag, classes), []).append(node_index)

    tables: list[Table] = []
    for members in groups.values():
        if len(members) < MIN_RECORDS:
            continue
        if any(_nearest_table(document, m) >= 0 for m in members):
            continue  # a real table already covered it

        records = [_record_cells(document, m) for m in members]
        records = [r for r in records if len(r) >= 2]
        if len(records) < MIN_RECORDS:
            continue
        # Every record has to have the same shape, or this is a coincidence
        # of styling rather than a repeated row.
        widths = {len(r) for r in records}
        if len(widths) != 1:
            continue

        tables.append(
            Table(
                headers=(),
                rows=tuple(Row(cells=tuple(("", c) for c in r)) for r in records),
            )
        )
    return tables


def _record_cells(document: Document, node_index: int) -> list[str]:
    """The distinct text pieces inside one record, as its cells."""
    cells: list[str] = []
    for child in document.children.get(node_index, ()):
        if not document.is_element(child) or not _shown(document, child):
            continue
        text = document.text_of(child, limit=120)
        if text:
            cells.append(text)
    return cells


# --- label/value pairs ------------------------------------------------------


def _pairs(document: Document, tables: list[Table], transient: set[int]) -> list[Pair]:
    pairs: list[Pair] = []

    # Every table row, flattened against its headers. This is the one that
    # turns the billing replica's sixth cell into an answer.
    for table in tables:
        for row in table.rows:
            for header, value in row.cells:
                if header and value:
                    pairs.append(Pair(label=header, value=value))

    for node_index in range(len(document)):
        if not document.is_element(node_index) or not _shown(document, node_index, transient):
            continue
        tag = document.tag(node_index)

        if tag == "dl":
            pairs += _definition_pairs(document, node_index)
        elif tag == "tr" or document.attribute(node_index, "role") == "row":
            pairs += _header_cell_pairs(document, node_index)

    seen: set[tuple[str, str]] = set()
    unique: list[Pair] = []
    for pair in pairs:
        key = (pair.label, pair.value)
        if key not in seen:
            seen.add(key)
            unique.append(pair)
    return unique


def _definition_pairs(document: Document, list_index: int) -> list[Pair]:
    pairs: list[Pair] = []
    label = ""
    for child in document.children.get(list_index, ()):
        tag = document.tag(child)
        if tag == "dt":
            label = document.text_of(child, limit=120)
        elif tag == "dd" and label:
            value = document.text_of(child, limit=200)
            if value:
                pairs.append(Pair(label=label, value=value))
    return pairs


def _header_cell_pairs(document: Document, row_index: int) -> list[Pair]:
    """`<th>Consumer name</th><td>...</td>` — a label and its value in a row.

    Repeats across the row, because a portal will happily put two or three
    label/value pairs side by side in one `tr`.
    """
    pairs: list[Pair] = []
    label = ""
    for child in document.children.get(row_index, ()):
        if not document.is_element(child):
            continue
        tag = document.tag(child)
        role = document.attribute(child, "role")
        text = document.text_of(child, limit=200)
        if tag == "th" or role in HEADER_ROLES:
            label = text
        elif (tag == "td" or role in CELL_ROLES) and label:
            if text:
                pairs.append(Pair(label=label, value=text))
            label = ""
    return pairs


# --- prominent values -------------------------------------------------------


def _prominent(document: Document, transient: set[int]) -> list[Value]:
    sizes: list[float] = []
    candidates: list[tuple[int, float]] = []

    for node_index, style in document.styles.items():
        if node_index in transient:
            continue
        if not document.is_element(node_index) or not visible(style):
            continue
        size = _px(style.get("font-size"))
        if size is None:
            continue
        # Only nodes with their own text, so a wrapper does not inherit its
        # child's prominence and get reported twice.
        if not _has_direct_text(document, node_index):
            continue
        sizes.append(size)
        candidates.append((node_index, size))

    if len(sizes) < 3:
        return []

    baseline = median(sizes)
    threshold = baseline * PROMINENCE_RATIO

    values: list[Value] = []
    seen: set[str] = set()
    for node_index, size in sorted(candidates, key=lambda c: -c[1]):
        if size < threshold:
            break
        if document.tag(node_index) in HEADING_TAGS:
            continue  # already reported as a heading
        text = document.text_of(node_index, limit=MAX_VALUE_CHARS + 1)
        if not text or len(text) > MAX_VALUE_CHARS or text in seen:
            continue
        seen.add(text)
        values.append(Value(text=text, font_size=size))
    return values


def _has_direct_text(document: Document, node_index: int) -> bool:
    return any(
        document.node_types[child] == 3 and document.node_values[child].strip()
        for child in document.children.get(node_index, ())
    )


def _px(value: str | None) -> float | None:
    if not value or not value.endswith("px"):
        return None
    try:
        return float(value[:-2])
    except ValueError:
        return None


def _shown(document: Document, node_index: int, transient: set[int] = frozenset()) -> bool:
    """Whether the node is displayed content. No box, or floating: neither."""
    if node_index in transient:
        return False
    style = document.styles.get(node_index)
    return style is not None and visible(style)
