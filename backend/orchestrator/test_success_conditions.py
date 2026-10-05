"""The check that would have caught the wrong answer.

On 2026-09-09 an LLM run set the railways date to the 15th of September,
searched, got two real trains back, and reported `task.completed` against a
goal naming the 15th of October. Every check the loop had agreed: results
existed, the page had changed, nothing had lapsed since the last look.

`rows_at_least=1` is satisfied by a search for any date at all, and the date
is not in the results table to be checked. These tests rebuild that exact
snapshot and assert the run would now fail instead.

Since 2026-09-17 the date is declared in `About.holds` rather than in the
success expectation, alongside what the task asks to find out, and `unmet` is
the check the loop runs. The second half of this file is about that: that a
value declared once is checked without being declared again, and that a task
cannot be written without saying what it is about.

No browser and no network: the failure is entirely a question of what a
`Snapshot` says and what a `Task` asks of it.
"""

from dataclasses import replace

import pytest

from backend.orchestrator.loop import (
    Snapshot,
    Task,
    findings_in,
    mismatch,
    said_so_far,
    satisfies,
    unmet,
)
from backend.orchestrator.plan import About, Answer, Expectation, FieldValue, Shown
from backend.orchestrator.railways_plan import (
    DEPARTURE_AS_SHOWN,
    RAILWAYS_TASK,
)
from backend.perception.content import Content, Pair, Row, Table

# The results the wrong search actually returned, headers and all.
RESULTS = Content(
    tables=[
        Table(
            headers=("Train No.", "From/To", "Time", "Duration"),
            rows=(
                Row(cells=(("Train No.", "2DN"),
                           ("From/To", "LAHORE CANTT KARACHI CANTT"),
                           ("Time", "08:04 06:20"),
                           ("Duration", "22 h 16 min"))),
                Row(cells=(("Train No.", "14DN"),
                           ("From/To", "LAHORE CANTT KARACHI CANTT"),
                           ("Time", "19:09 19:25"),
                           ("Duration", "24 h 16 min"))),
            ),
        )
    ]
)

LABELS = ("Home", "Train Timings", "From", "To", "Departure Date", "")


def railways_page(date_shown: str) -> Snapshot:
    """The live search page as it stood at the end of that run.

    The URL and title never change on this site — it is a single-page app —
    which is why neither can be part of a success condition here.
    """
    return Snapshot(
        url="https://www.pakrailways.gov.pk/train",
        title="RABTA",
        labels=LABELS,
        values=("", "", "LAHORE CANTT", "KARACHI CANTT", date_shown, ""),
        content=RESULTS,
    )


WRONG_MONTH = railways_page("15-09-2026")
RIGHT_MONTH = railways_page(DEPARTURE_AS_SHOWN)


# --- the exact failing case -------------------------------------------------


def test_a_search_on_the_wrong_date_no_longer_counts_as_success() -> None:
    """The regression this exists for, stated as an assertion."""
    reason = unmet(WRONG_MONTH, RAILWAYS_TASK)
    assert reason is not None
    assert "Departure Date" in reason
    assert "15-09-2026" in reason
    assert DEPARTURE_AS_SHOWN in reason


def test_the_old_condition_would_have_let_it_through() -> None:
    """Which check was too weak, pinned down rather than asserted in prose.

    Same page, same results. `rows_at_least=1` passes on it. That is not a
    bug in `rows_at_least` — it answers the question it was asked. It is the
    wrong question for a goal that names a date.
    """
    assert satisfies(WRONG_MONTH, Expectation(rows_at_least=1))


def test_the_right_date_with_results_does_succeed() -> None:
    """The control: the condition is not simply unsatisfiable."""
    assert unmet(RIGHT_MONTH, RAILWAYS_TASK) is None


def test_both_halves_are_load_bearing() -> None:
    """A filled form nobody searched with is not success either."""
    filled_but_unsearched = Snapshot(
        url="https://www.pakrailways.gov.pk/train",
        title="RABTA",
        labels=LABELS,
        values=("", "", "LAHORE CANTT", "KARACHI CANTT", DEPARTURE_AS_SHOWN, ""),
        content=Content(),
    )

    dates_only = replace(RAILWAYS_TASK, success=None)
    assert unmet(filled_but_unsearched, dates_only) is None
    assert unmet(filled_but_unsearched, RAILWAYS_TASK) is not None


# --- a held value on its own ------------------------------------------------


def test_an_empty_field_is_an_answer_not_an_absence() -> None:
    """A field the page has emptied is exactly what this is for."""
    emptied = railways_page("")

    reason = unmet(emptied, RAILWAYS_TASK)
    assert "it holds ''" in reason


def test_a_missing_field_says_so_rather_than_passing() -> None:
    """Absent and empty are different, and neither is success."""
    gone = Snapshot(url="u", title="t", labels=("Something else",), values=("x",))

    task = Task(goal="g", estimated_steps=1,
                about=About(holds=(FieldValue("Departure Date", "x"),)))
    reason = unmet(gone, task)
    assert "expected a field called 'Departure Date'" in reason


def test_the_expected_value_is_what_the_page_shows_not_what_was_typed() -> None:
    """The distinction the widget forces.

    The picker accepts `2026-10-15` and writes back `15-10-2026`. A condition
    written against the typed string would fail at the moment the value became
    real, which is the opposite of what it is for.
    """
    assert RAILWAYS_TASK.about.holds[0].equals == DEPARTURE_AS_SHOWN
    assert unmet(railways_page("2026-10-15"), RAILWAYS_TASK) is not None


@pytest.mark.parametrize("held", ["15-10-2026 ", " 15-10-2026", "15-10-26", "15/10/2026"])
def test_a_near_miss_is_still_a_miss(held: str) -> None:
    """Exact, deliberately. A date that is nearly right is a wrong answer."""
    assert unmet(railways_page(held), RAILWAYS_TASK) is not None


def test_value_of_reads_the_field_by_its_label() -> None:
    assert WRONG_MONTH.value_of("Departure Date") == "15-09-2026"
    assert WRONG_MONTH.value_of("From") == "LAHORE CANTT"
    assert WRONG_MONTH.value_of("Nothing called this") is None


def test_an_expectation_with_no_value_check_ignores_values() -> None:
    """Every existing task is unaffected."""
    assert satisfies(WRONG_MONTH, Expectation(rows_at_least=1))
    assert satisfies(WRONG_MONTH, Expectation())


# --- one declaration of what a task is about --------------------------------


def test_a_task_cannot_be_written_without_saying_what_it_is_about() -> None:
    """Forgetting is loud now.

    `Task.answers` and `Expectation.value_is` both defaulted to nothing, so a
    task that left either out checked nothing and showed nothing, and said so
    nowhere. `about` has no default.
    """
    with pytest.raises(TypeError):
        Task(goal="Find something.", estimated_steps=1)  # type: ignore[call-arg]


def test_a_named_value_is_checked_without_being_repeated_in_success() -> None:
    """The date is declared once, in `about`, and the success expectation
    does not mention it — and the wrong date still fails."""
    assert RAILWAYS_TASK.success == Expectation(rows_at_least=1)
    assert satisfies(WRONG_MONTH, RAILWAYS_TASK.success)
    assert unmet(WRONG_MONTH, RAILWAYS_TASK) is not None


def test_a_task_with_nothing_named_is_judged_by_success_alone() -> None:
    task = Task(goal="g", estimated_steps=1, success=Expectation(rows_at_least=1),
                about=About())
    assert unmet(WRONG_MONTH, task) is None


def test_what_a_task_finds_comes_from_the_same_declaration() -> None:
    """`finds` is read by name from the content channel, in declared order."""
    page = Snapshot(
        url="u", title="t", labels=(), values=(),
        content=Content(pairs=[Pair("Duration", "22 h 16 min"), Pair("Train No.", "2DN")]),
    )
    found = findings_in(page, RAILWAYS_TASK, {})
    assert [(f.label, f.value) for f in found] == [("Train", "2DN"), ("Journey", "22 h 16 min")]


def test_a_finding_is_remembered_after_the_page_stops_showing_it() -> None:
    """The billing amount is on the results page; the run ends on another."""
    task = Task(goal="g", estimated_steps=1,
                about=About(finds=(Answer("Your bill", reads="P/WITHIN"),)))
    known: dict[str, str] = {}
    results = Snapshot(url="u", title="t", labels=(),
                       content=Content(pairs=[Pair("P/WITHIN", "14,382")]))
    detail = Snapshot(url="u2", title="t", labels=(), content=Content())

    findings_in(results, task, known)
    found = findings_in(detail, task, known)

    assert [(f.label, f.value) for f in found] == [("Your bill", "14,382")]


# --- a finding carries every value, not the first ---------------------------


def test_a_finding_carries_every_train_the_page_listed() -> None:
    """"Which trains run?" is answered by all of them.

    The 2026-09-09 search returned two and the finding named one
    (EVALUATION.md, 2026-09-18b).
    """
    page = Snapshot(
        url="u", title="t", labels=(), values=(),
        content=Content(pairs=[
            Pair("Train No.", "2DN"), Pair("Duration", "22 h 16 min"),
            Pair("Train No.", "14DN"), Pair("Duration", "24 h 16 min"),
        ]),
    )

    found = findings_in(page, RAILWAYS_TASK, {})

    assert [(f.label, f.value) for f in found] == [
        ("Train", "2DN, 14DN"),
        ("Journey", "22 h 16 min, 24 h 16 min"),
    ]


def test_a_long_list_says_how_many_are_left_rather_than_filling_the_screen() -> None:
    """The closing screen shows a finding in its largest type. Twenty values
    would not be readable at a glance, which is the point of showing it."""
    from backend.orchestrator.voice import SHOWN_VALUES, found

    assert found(["2DN"]) == "2DN"
    assert found(["a", "b", "c", "d"]) == "a, b, c, d"
    assert found(["a", "b", "c", "d", "e"]) == "a, b, c, d and 1 more"
    assert found([str(n) for n in range(10)]).endswith(f"and {10 - SHOWN_VALUES} more")


def test_one_value_reads_exactly_as_it_did_before() -> None:
    """The billing amount is one number, and must still arrive as one number."""
    page = Snapshot(url="u", title="t", labels=(),
                    content=Content(pairs=[Pair("P/WITHIN", "14,382")]))
    task = Task(goal="g", estimated_steps=1,
                about=About(finds=(Answer("Your bill", reads="P/WITHIN"),)))

    assert [(f.label, f.value) for f in findings_in(page, task, {})] == [("Your bill", "14,382")]


# --- and the results whole, a row per result ---------------------------------
#
# `values` drops a repeated value, so the closing screen cannot pair two
# findings' lists by position. The first finding carries the rows (2026-10-05).


def results_page(*rows: tuple[str, str]) -> Snapshot:
    """A results table, with its rows also flattened to pairs as `extract`
    does."""
    headers = ("Train No.", "Duration")
    table = Table(headers=headers,
                  rows=tuple(Row(cells=tuple(zip(headers, row))) for row in rows))
    pairs = [Pair(name, value) for row in table.rows for name, value in row.cells]
    return Snapshot(url="u", title="t", labels=(), values=(),
                    content=Content(tables=[table], pairs=pairs))


def test_two_trains_with_one_journey_time_each_carry_it() -> None:
    page = results_page(("3UP", "5 h 15 min"), ("4DN", "5 h 15 min"))

    found = findings_in(page, RAILWAYS_TASK, {}, [])

    assert [f.values for f in found] == [["3UP", "4DN"], ["5 h 15 min"]]
    assert found[0].rows == [["3UP", "5 h 15 min"], ["4DN", "5 h 15 min"]]
    assert found[1].rows == []


def test_repeats_on_different_rows_keep_each_train_its_own_time() -> None:
    page = results_page(("11UP", "3 h 15 min"), ("12DN", "4 h 15 min"),
                        ("13UP", "3 h 15 min"), ("14DN", "4 h 15 min"))

    found = findings_in(page, RAILWAYS_TASK, {}, [])

    assert found[1].values == ["3 h 15 min", "4 h 15 min"]
    assert found[0].rows == [["11UP", "3 h 15 min"], ["12DN", "4 h 15 min"],
                             ["13UP", "3 h 15 min"], ["14DN", "4 h 15 min"]]


def test_the_rows_are_remembered_after_the_page_stops_showing_them() -> None:
    known: dict[str, list[str]] = {}
    rows: list[dict[str, str]] = []
    findings_in(results_page(("3UP", "5 h 15 min"), ("4DN", "5 h 15 min")),
                RAILWAYS_TASK, known, rows)

    found = findings_in(Snapshot(url="u2", title="t", labels=(), content=Content()),
                        RAILWAYS_TASK, known, rows)

    assert found[0].rows == [["3UP", "5 h 15 min"], ["4DN", "5 h 15 min"]]
    assert rows == [{"Train": "3UP", "Journey": "5 h 15 min"},
                    {"Train": "4DN", "Journey": "5 h 15 min"}]


def test_values_not_from_a_table_carry_no_rows() -> None:
    """Label/value pairs have no rows to keep; the message is as it was."""
    page = Snapshot(url="u", title="t", labels=(), values=(), content=Content(pairs=[
        Pair("Train No.", "2DN"), Pair("Duration", "22 h 16 min")]))

    found = findings_in(page, RAILWAYS_TASK, {}, [])

    assert [f.rows for f in found] == [[], []]


# --- and the message carries the values themselves --------------------------
#
# `value` is one line, and one line has to stop somewhere: past four values it
# counts the rest. That is right for the step screen, which shows a finding
# while the run is still going, and wrong for the closing screen, which is the
# answer. So the message carries both.


def test_a_finding_carries_the_values_as_well_as_the_line() -> None:
    page = Snapshot(
        url="u", title="t", labels=(), values=(),
        content=Content(pairs=[
            Pair("Train No.", "2DN"), Pair("Duration", "22 h 16 min"),
            Pair("Train No.", "14DN"), Pair("Duration", "24 h 16 min"),
        ]),
    )

    found = findings_in(page, RAILWAYS_TASK, {})

    assert [f.values for f in found] == [["2DN", "14DN"],
                                         ["22 h 16 min", "24 h 16 min"]]
    assert found[0].value == "2DN, 14DN"


def test_nothing_is_dropped_however_many_results_there_are() -> None:
    """Nine trains: the line counts the rest, the list keeps all nine."""
    trains = [f"{n}UP" for n in range(1, 10)]
    page = Snapshot(
        url="u", title="t", labels=(), values=(),
        content=Content(pairs=[Pair("Train No.", train) for train in trains]),
    )
    task = Task(goal="g", estimated_steps=1,
                about=About(finds=(Answer("Train", reads="Train No."),)))

    found = findings_in(page, task, {})

    assert found[0].values == trains
    assert found[0].value.endswith("and 5 more")


def test_one_value_arrives_as_a_list_of_one() -> None:
    """A screen that shows every value needs no special case for one."""
    page = Snapshot(url="u", title="t", labels=(),
                    content=Content(pairs=[Pair("P/WITHIN", "14,382")]))
    task = Task(goal="g", estimated_steps=1,
                about=About(finds=(Answer("Your bill", reads="P/WITHIN"),)))

    found = findings_in(page, task, {})

    assert found[0].values == ["14,382"]
    assert found[0].value == "14,382"


def test_the_values_are_remembered_with_the_line() -> None:
    """The run's memory holds the list, so a page that no longer shows the
    results does not shrink the answer back to one line."""
    task = Task(goal="g", estimated_steps=1,
                about=About(finds=(Answer("Train", reads="Train No."),)))
    known: dict[str, list[str]] = {}
    results = Snapshot(url="u", title="t", labels=(), content=Content(
        pairs=[Pair("Train No.", "2DN"), Pair("Train No.", "14DN")]))
    later = Snapshot(url="u2", title="t", labels=(), content=Content())

    findings_in(results, task, known)
    found = findings_in(later, task, known)

    assert found[0].values == ["2DN", "14DN"]


# --- the person's own values, checked in their own words --------------------
#
# Until 2026-09-30 the values a run checked were the plan's. A goal of "trains
# to Rawalpindi tomorrow" was checked against Lahore Cantt to Karachi Cantt on
# the 15th of next month, so a run that searched a journey nobody had asked
# about passed every check it had. Three things were needed before a person's
# own values could be checked at all, and each is one group below.


def station_page(origin: str, destination: str, date_shown: str) -> Snapshot:
    return Snapshot(
        url="https://www.pakrailways.gov.pk/train",
        title="RABTA",
        labels=LABELS,
        values=("", "", origin, destination, date_shown, ""),
        content=RESULTS,
    )


def asked_for(origin: str, destination: str, date_shown: str) -> Task:
    """A task naming the person's own words, the way `trip_task` declares them."""
    return Task(
        goal=f"Find trains from {origin} to {destination}.",
        estimated_steps=5,
        success=Expectation(rows_at_least=1),
        about=About(holds=(
            FieldValue("Departure Date", date_shown),
            FieldValue("From", origin, names=True),
            FieldValue("To", destination, names=True),
        )),
    )


def test_a_place_the_person_named_is_met_by_the_station_the_site_calls_it() -> None:
    """They type "Lahore" and the site holds `LAHORE JN`. Which Lahore station
    they meant was settled by asking, so the box only has to name the place."""
    task = asked_for("Lahore", "Rawalpindi", "01-10-2026")
    assert unmet(station_page("LAHORE JN", "RAWALPINDI", "01-10-2026"), task) is None
    assert unmet(station_page("LAHORE CANTT", "RAWALPINDI", "01-10-2026"), task) is None


def test_a_search_for_another_route_fails_rather_than_completes() -> None:
    """The route half of the defect this file exists for: results came back,
    and they are for a journey nobody asked about."""
    wrong_route = station_page("LAHORE CANTT", "KARACHI CANTT", "01-10-2026")

    reason = unmet(wrong_route, asked_for("Lahore", "Rawalpindi", "01-10-2026"))

    assert reason is not None
    assert "'To'" in reason and "Rawalpindi" in reason and "KARACHI CANTT" in reason
    # And the check it slips past, so the two are never confused.
    assert satisfies(wrong_route, Expectation(rows_at_least=1))


def test_a_loosely_matched_place_is_not_a_free_pass() -> None:
    """`names` means "this field names that place", not "anything will do"."""
    task = asked_for("Lahore", "Rawalpindi", "01-10-2026")
    assert unmet(station_page("LAHORE JN", "ROHRI JN", "01-10-2026"), task) is not None
    assert unmet(station_page("MULTAN CANTT", "RAWALPINDI", "01-10-2026"), task) is not None


def test_the_day_stays_exact_while_the_places_loosen() -> None:
    """Two kinds of value in one task. A date that is nearly right is still a
    wrong answer, whatever the stations say."""
    task = asked_for("Lahore", "Rawalpindi", "01-10-2026")

    reason = unmet(station_page("LAHORE JN", "RAWALPINDI", "1-10-2026"), task)

    assert reason is not None and "Departure Date" in reason
    assert FieldValue("Departure Date", "01-10-2026").accepts("01-10-2026")
    assert not FieldValue("Departure Date", "01-10-2026").accepts("01-10-2026 ")


def test_a_named_place_is_matched_whatever_the_case() -> None:
    assert FieldValue("From", "Lahore", names=True).accepts("LAHORE JN")
    assert FieldValue("From", "lahore", names=True).accepts("Lahore Jn")
    assert not FieldValue("From", "Lahore", names=True).accepts("")


# --- a value in no field by the end: what the site said back ----------------


REFERENCE = "04141234567890"


def bill_results(reference: str) -> Snapshot:
    """The results page, which prints the reference number it looked up."""
    return Snapshot(
        url="http://127.0.0.1:5100/bill", title="Bill", labels=(), values=(),
        content=Content(pairs=[Pair("REF NO", reference), Pair("P/WITHIN", "14,382")]),
    )


BILL_DETAIL = Snapshot(
    url="http://127.0.0.1:5100/bill/detail", title="Bill Detail",
    labels=(), values=(), content=Content(pairs=[Pair("Amount", "14,382")]),
)


def looking_up(reference: str) -> Task:
    return Task(
        goal=f"Find the amount due for reference number {reference}.",
        estimated_steps=3,
        success=Expectation(url_contains="/bill/detail", title_contains="Bill Detail"),
        about=About(shows=(Shown(reads="REF NO", says=reference),)),
    )


def test_the_bill_that_was_looked_up_has_to_be_the_one_asked_about() -> None:
    """The case `holds` cannot reach. The reference number is typed on the
    first page and the run ends two pages later with no field left to check
    it in, so what is checked is what the site said back (`About`)."""
    task = looking_up(REFERENCE)
    seen: dict[str, list[str]] = {}

    said_so_far(bill_results(REFERENCE), task, seen)

    assert unmet(BILL_DETAIL, task, seen) is None


def test_someone_elses_bill_fails_rather_than_completes() -> None:
    task = looking_up(REFERENCE)
    seen: dict[str, list[str]] = {}

    said_so_far(bill_results("04149999999999"), task, seen)
    reason = unmet(BILL_DETAIL, task, seen)

    assert reason is not None
    assert "REF NO" in reason and REFERENCE in reason and "04149999999999" in reason


def test_a_page_that_never_said_it_is_not_success_either() -> None:
    """Nothing said is not the same as the right thing said."""
    reason = unmet(BILL_DETAIL, looking_up(REFERENCE), {})
    assert reason is not None and "nothing" in reason


def test_without_the_runs_memory_only_this_page_is_asked() -> None:
    """`unmet` on its own looks at one page, as it always has."""
    task = looking_up(REFERENCE)
    assert unmet(bill_results(REFERENCE), replace(task, success=None)) is None
    assert unmet(BILL_DETAIL, task) is not None


def test_a_task_that_only_names_what_must_be_shown_is_still_checked() -> None:
    """With no success expectation and nothing held, `shows` alone decides —
    the registration case, where the course is chosen by pressing its button
    and the confirmation is the only thing that names it."""
    task = Task(goal="g", estimated_steps=1,
                about=About(shows=(Shown(reads="Course", says="CS-401"),)))
    said = Snapshot(url="u", title="t", labels=(), values=(),
                    content=Content(pairs=[Pair("Course", "CS-401 section 001")]))
    another = Snapshot(url="u", title="t", labels=(), values=(),
                       content=Content(pairs=[Pair("Course", "MT-201")]))

    assert unmet(said, task) is None
    assert unmet(another, task) is not None


def test_what_the_site_said_is_remembered_across_pages() -> None:
    """The same reason findings are remembered: the page that says it is
    usually not the page the run ends on."""
    task = looking_up(REFERENCE)
    seen: dict[str, list[str]] = {}

    said_so_far(Snapshot(url="u", title="t", labels=(), values=(), content=Content()),
                task, seen)
    said_so_far(bill_results(REFERENCE), task, seen)
    said_so_far(BILL_DETAIL, task, seen)

    assert seen["REF NO"] == [REFERENCE]
    assert unmet(BILL_DETAIL, task, seen) is None


def test_a_shown_value_is_met_inside_a_longer_one() -> None:
    """A site puts its own words round a value: `CS-401 section 001`. The cost
    of matching inside is that a longer code containing this one would also
    pass; the portal's codes are all one shape, so nothing here relies on it."""
    assert Shown(reads="Course", says="CS-401").met_by(["CS-401 section 001"])
    assert Shown(reads="Course", says="cs-401").met_by(["CS-401"])
    assert Shown(reads="Course", says="CS-401").met_by(["CS-4010"])
    assert not Shown(reads="Course", says="CS-401").met_by([])
    assert not Shown(reads="Course", says="CS-401").met_by(["MT-201", "CS-402"])


# --- a page that has to have offered something ------------------------------


def test_a_step_that_types_a_name_expects_the_page_to_offer_it() -> None:
    """`label_like`: typing "LAHORE" into the station box has to bring a
    station list back before there is anything to choose. The site's labels
    are its own words, so the match is loose and ignores case."""
    offered = Snapshot(url="u", title="t",
                       labels=("LAHORE JN", "LAHORE CANTT"), values=("", ""))
    nothing = Snapshot(url="u", title="t", labels=("From", "To"), values=("", ""))

    assert satisfies(offered, Expectation(label_like="Lahore"))
    assert not satisfies(nothing, Expectation(label_like="Lahore"))
    reason = mismatch(nothing, Expectation(label_like="Lahore"))
    assert reason is not None and "Lahore" in reason


def test_the_strict_check_is_the_one_a_station_list_defeats() -> None:
    """Why `label_like` was needed at all: the site's label for a place is
    never the word that was typed for it."""
    offered = Snapshot(url="u", title="t", labels=("LAHORE JN",), values=("",))
    assert satisfies(offered, Expectation(label_like="Lahore"))
    assert not satisfies(offered, Expectation(label_present="Lahore"))


def test_an_expectation_with_no_loose_label_ignores_labels() -> None:
    """Every existing step is unaffected."""
    assert satisfies(WRONG_MONTH, Expectation())
