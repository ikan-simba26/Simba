"""B3 (2026-11-18): when the person changes one earlier answer the task starts
again and the other answers are kept — a matching question is answered by its
earlier answer, never a final screen or a read-back, each answer used once."""

from types import SimpleNamespace

from backend.orchestrator.loop import Expectation, Move, _Run
from shared.schema import StepAction, StepField, Detail


def question(text: str, labels: list[str], *, kind=None, fields=None) -> Move:
    return Move(instruction=text, detail="", operations=[], expect=Expectation(),
                fields=fields or [],
                actions=[StepAction(id=f"choice:{i}", label=l, kind="primary")
                         for i, l in enumerate(labels)],
                question=True, kind=kind)


def run_with(kept):
    return SimpleNamespace(connection=SimpleNamespace(keep_answers=kept))


def ask(run, move, final=None):
    return _Run.kept_answer(run, move, 3, final)


def test_a_matching_question_is_answered_by_the_earlier_answer_found_by_its_words() -> None:
    run = run_with([{"question": "Which Lahore station do you mean?", "action_label": "Lahore Jn."}])
    # The list is in another order now: the words decide, never the position.
    move = question("Which Lahore station do you mean?", ["Lahore Cantt", "Lahore Jn."])
    assert ask(run, move) == {"step_index": 3, "action_id": "choice:1", "input_values": {}}


def test_each_kept_answer_is_used_once() -> None:
    run = run_with([{"question": "Which one?", "action_label": "A"}])
    move = question("Which one?", ["A", "B"])
    assert ask(run, move) is not None
    assert ask(run, move) is None


def test_a_question_that_is_not_in_the_kept_answers_is_asked() -> None:
    run = run_with([{"question": "Which Lahore station do you mean?", "action_label": "Lahore Jn."}])
    assert ask(run, question("Which Karachi station do you mean?", ["Karachi City"])) is None


def test_a_button_that_is_no_longer_offered_is_asked_not_guessed() -> None:
    run = run_with([{"question": "Which one?", "action_label": "Gone"}])
    assert ask(run, question("Which one?", ["A", "B"])) is None


def test_a_final_screen_is_never_answered_for_the_person() -> None:
    run = run_with([{"question": "I'll order it.", "action_label": "Do it"}])
    move = question("I'll order it.", ["Do it", "Don't"])
    assert ask(run, move, final=[Detail(label="Total", value="Rs 4195")]) is None


def test_a_read_back_is_never_answered_for_the_person() -> None:
    run = run_with([{"question": "Lahore to Karachi, Friday. Is that right?",
                     "action_label": "Yes, that's right"}])
    move = question("Lahore to Karachi, Friday. Is that right?", ["Yes, that's right"],
                    kind="confirm")
    assert ask(run, move) is None


def test_typed_values_are_kept_with_the_answer() -> None:
    run = run_with([{"question": "What is the reference?", "action_label": "Use this",
                     "input_values": {"reference": "0414"}}])
    move = question("What is the reference?", ["Use this"],
                    fields=[StepField(id="reference", label="Reference", type="text", value="")])
    assert ask(run, move)["input_values"] == {"reference": "0414"}


def test_no_kept_answers_means_everything_is_asked() -> None:
    assert ask(run_with(None), question("Which one?", ["A"])) is None
    assert ask(SimpleNamespace(connection=SimpleNamespace()), question("Which one?", ["A"])) is None
