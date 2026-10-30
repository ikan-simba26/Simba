"""The provisional level rules, driven by scripted telemetry.

No browser and no page: a run here is a list of what the overlay would have
sent — a timer sample every three seconds while a step waits, and one more
with the answer — fed to `LevelRules` in order. What is asserted is the level
the person would have been looking at, and which decisions would have reached
the frontend as `load.updated`.

The four runs the task named are the first four tests. Everything after them
pins down one rule each.
"""

from dataclasses import replace

from backend.estimator.page_features import PageFeatures
from backend.estimator.page_model import PageModel
from backend.estimator.rules import RULES_VERSION, THRESHOLDS, Decision, LevelRules

#: Billing's first page as the host reads it (`data/corpus.json`): an
#: ordinary page, not a heavy one.
LIGHT = PageFeatures(
    interactive=6, links=31, inferred=0, text_density=1.728, max_depth=9,
    overlays=0, form_fields=1, dead_link_ratio=0.9, reading_grade=7.7,
    controls=37, dead_links=28, characters=2600, viewport_characters=2400,
    words=400, sentences=90, syllables=700,
)

#: The registration replica just after signing in: dense text and a modal.
HEAVY = PageFeatures(
    interactive=21, links=45, inferred=0, text_density=4.81, max_depth=11,
    overlays=1, form_fields=0, dead_link_ratio=0.978, reading_grade=6.41,
    controls=66, dead_links=44, characters=5299, viewport_characters=4929,
    words=680, sentences=202, syllables=1192,
)


def sample(step: int, ms: int, *, answered: bool = False, ratio: float = 1.0,
           backtracks: int = 0, help_presses: int = 0) -> dict:
    return {
        "step_index": step, "hesitation_ms": ms, "cursor_path_ratio": ratio,
        "backtracks": backtracks, "rereads": 0, "help_presses": help_presses,
        "answered": answered,
    }


def calm_step(step: int) -> list[dict]:
    """Read it, pressed it: one timer tick at most, answered in two seconds."""
    return [sample(step, 2000, answered=True)]


def hesitant_step(step: int) -> list[dict]:
    """Nothing for twenty seconds, the pointer wandering, then an answer."""
    return [
        sample(step, 3000),
        sample(step, 6000, ratio=2.0, backtracks=1),
        sample(step, 9000, ratio=3.5, backtracks=3),
        sample(step, 12000, ratio=4.0, backtracks=4),
        sample(step, 15000, ratio=5.0, backtracks=5),
        sample(step, 18000, ratio=5.5, backtracks=5),
        sample(step, 21000, ratio=5.5, backtracks=6, answered=True),
    ]


class Run:
    """Plays a scripted run through the rules, the way the loop calls them."""

    def __init__(self, rules: LevelRules | None = None) -> None:
        self.rules = rules or LevelRules()
        self.decisions: list[Decision] = []
        #: The level on screen for each step, as it was when that step was
        #: answered.
        self.levels: dict[int, int] = {}

    @property
    def sent(self) -> list[Decision]:
        return [d for d in self.decisions if d.send]

    def step(self, index: int, samples: list[dict], page: PageFeatures = LIGHT) -> None:
        self.decisions.append(self.rules.start_step(index, page))
        for payload in samples:
            self.decisions.append(self.rules.telemetry(payload))
        self.levels[index] = self.rules.level

    def end(self) -> None:
        self.decisions.append(self.rules.end())


# --- the four runs --------------------------------------------------------------


def test_a_calm_run_stays_at_level_2() -> None:
    run = Run()
    for index in range(1, 6):
        run.step(index, calm_step(index))
    run.end()

    assert set(run.levels.values()) == {2}
    # Said once, at the start, so the overlay and the backend agree; never
    # again, because nothing moved.
    assert [(d.at, d.level) for d in run.sent] == [("start", 2)]
    assert not any(d.changed for d in run.decisions)


def test_a_hesitant_run_folds_to_3() -> None:
    run = Run()
    run.step(1, calm_step(1))
    run.step(2, hesitant_step(2))

    assert run.levels == {1: 2, 2: 3}
    folds = [d for d in run.sent if d.at != "start"]
    assert len(folds) == 1
    fold = folds[0]
    # During the step, on the timer, not after the answer: the person who is
    # stuck gets the simpler screen while they are stuck.
    assert (fold.at, fold.step_index, fold.level_before, fold.level) == ("waiting", 2, 2, 3)
    assert fold.inputs["telemetry"]["hesitation_ms"] == THRESHOLDS.hesitation_ms


def test_a_run_that_calms_down_returns_to_2_only_after_two_calm_steps() -> None:
    run = Run()
    run.step(1, hesitant_step(1))
    run.step(2, calm_step(2))
    # One calm step is not enough.
    assert run.levels == {1: 3, 2: 3}
    run.step(3, calm_step(3))
    # The second calm step has been answered, but its screen does not reshape
    # as it leaves: the return happens as the next step arrives.
    assert run.levels[3] == 3
    run.step(4, calm_step(4))
    assert run.levels[4] == 2

    back = [d for d in run.sent if d.level_before == 3 and d.level == 2]
    assert len(back) == 1
    assert (back[0].at, back[0].step_index) == ("step", 4)


def test_a_locked_level_never_moves() -> None:
    run = Run()
    run.decisions.append(run.rules.override(2, locked=True))
    run.step(1, hesitant_step(1), page=HEAVY)
    run.step(2, [sample(2, 4000, help_presses=1, answered=True)])
    run.step(3, hesitant_step(3))
    run.end()

    assert set(run.levels.values()) == {2}
    assert run.sent == []
    # Still decided and written down — what it would have done is the part a
    # trained model will be checked against — but never sent.
    assert any(d.rule == "locked" and "would" in d.reason for d in run.decisions)


# --- the starting level -----------------------------------------------------------


def test_a_heavy_page_starts_simpler() -> None:
    run = Run()
    run.step(1, calm_step(1), page=HEAVY)

    start = run.decisions[0]
    assert (start.at, start.level, start.send) == ("start", 3, True)
    assert start.score == 1.0
    assert run.levels[1] == 3


def test_one_sign_of_a_heavy_page_is_not_enough() -> None:
    """Registration's sign-in page is dense (2.57) with nothing else heavy
    about it, and should not start the run simplified."""
    dense_only = PageFeatures(**{**LIGHT.__dict__, "text_density": 2.569})
    rules = LevelRules()
    assert rules.start_step(1, dense_only).level == 2


def test_a_heavy_start_comes_back_after_two_calm_steps() -> None:
    """The page guessed; the person's calm is better evidence than the guess."""
    run = Run()
    run.step(1, calm_step(1), page=HEAVY)
    run.step(2, calm_step(2))
    run.step(3, calm_step(3))

    assert run.levels == {1: 3, 2: 3, 3: 2}


def test_a_page_with_no_features_starts_at_level_2() -> None:
    rules = LevelRules()
    decision = rules.start_step(1, None)
    assert decision.level == 2 and decision.send


# --- each signal on its own -----------------------------------------------------------


def test_a_help_press_alone_folds() -> None:
    run = Run()
    run.step(1, [sample(1, 2500, help_presses=1)])
    assert run.levels[1] == 3


def test_a_wandering_pointer_alone_folds_once_the_step_has_been_up_a_while() -> None:
    run = Run()
    run.step(1, [sample(1, THRESHOLDS.wander_after_ms,
                        ratio=THRESHOLDS.wander_ratio)])
    assert run.levels[1] == 3


def test_backtracks_alone_fold_once_the_step_has_been_up_a_while() -> None:
    run = Run()
    run.step(1, [sample(1, THRESHOLDS.wander_after_ms,
                        backtracks=THRESHOLDS.wander_backtracks)])
    assert run.levels[1] == 3


def test_a_quick_answer_with_a_busy_pointer_is_not_a_signal() -> None:
    """The recorded rows have a 24.8 path ratio on a step answered in three
    seconds: a short hop divides by a short distance. It is noise until the
    step has been on screen long enough to be a pause."""
    run = Run()
    run.step(1, [sample(1, 3045, ratio=24.83, backtracks=9, answered=True)])
    assert run.levels[1] == 2


# --- simplify quickly, restore slowly ----------------------------------------------


def test_never_more_than_one_change_per_step() -> None:
    """Handed back at level 1, a struggling person moves to 2 — and not on to
    3 in the same step, however long it goes on."""
    run = Run()
    run.rules.start_step(1, LIGHT)
    run.rules.override(1, locked=False)
    for payload in hesitant_step(1):
        run.decisions.append(run.rules.telemetry(payload))
    run.decisions.append(run.rules.telemetry(sample(1, 30000, help_presses=2)))

    assert run.rules.level == 2
    assert [d.level for d in run.decisions if d.send] == [2]
    assert any(d.rule == "once-per-step" for d in run.decisions)
    # And the next step may move again.
    run.step(2, [sample(2, 16000)])
    assert run.levels[2] == 3


def test_a_step_that_restored_cannot_also_fold() -> None:
    run = Run()
    run.step(1, hesitant_step(1))
    run.step(2, calm_step(2))
    run.step(3, calm_step(3))
    run.step(4, hesitant_step(4))  # restored as it arrived

    assert run.levels[4] == 2
    run.step(5, hesitant_step(5))
    assert run.levels[5] == 3


def test_an_in_between_step_breaks_the_calm_streak() -> None:
    """Ten seconds is not a signal and not calm either. It starts the count
    again rather than counting as half of one."""
    run = Run()
    run.step(1, hesitant_step(1))
    run.step(2, calm_step(2))
    run.step(3, [sample(3, 10000, answered=True)])
    run.step(4, calm_step(4))
    assert run.levels[4] == 3
    run.step(5, calm_step(5))
    run.step(6, calm_step(6))
    assert run.levels[6] == 2


def test_a_step_that_signalled_on_the_timer_is_not_calm_when_answered() -> None:
    """Already at 3, so the signal moves nothing — but it still counts."""
    run = Run()
    run.step(1, hesitant_step(1))
    run.step(2, calm_step(2))
    run.step(3, [sample(3, 3000, help_presses=1), sample(3, 3500, answered=True,
                                                         help_presses=1)])
    run.step(4, calm_step(4))
    assert run.levels[4] == 3


def test_the_return_is_said_at_the_end_when_there_is_no_next_step() -> None:
    """Billing has three steps. Hesitate on the first and the second calm
    answer is the last one, so the return goes out before the ending."""
    run = Run()
    run.step(1, hesitant_step(1))
    run.step(2, calm_step(2))
    run.step(3, calm_step(3))
    run.end()

    last = run.decisions[-1]
    assert (last.at, last.level_before, last.level, last.send) == ("end", 3, 2, True)


def test_the_estimator_never_chooses_level_1() -> None:
    """More detail is the person's choice; the rules only restore to 2."""
    run = Run()
    for index in range(1, 10):
        run.step(index, calm_step(index))
    assert min(run.levels.values()) == 2


def test_level_1_handed_back_stays_there_while_calm() -> None:
    run = Run()
    run.rules.start_step(1, LIGHT)
    run.rules.override(1, locked=False)
    for payload in calm_step(1):
        run.rules.telemetry(payload)
    for index in range(2, 6):
        run.step(index, calm_step(index))
    assert set(run.levels.values()) == {1}


# --- the lock -------------------------------------------------------------------------


def test_unlocking_hands_the_level_back_at_whatever_the_person_chose() -> None:
    run = Run()
    run.rules.override(3, locked=True)
    run.step(1, calm_step(1))
    run.rules.override(3, locked=False)
    run.step(2, calm_step(2))
    run.step(3, calm_step(3))
    run.step(4, calm_step(4))
    # Unlocked at 3; two calm steps after that, it comes back to 2.
    assert run.levels == {1: 3, 2: 3, 3: 3, 4: 2}


def test_a_lock_set_before_the_first_step_holds_the_start() -> None:
    rules = LevelRules()
    rules.override(1, locked=True)
    start = rules.start_step(1, HEAVY)
    assert (start.level, start.send, start.rule) == (1, False, "locked")


# --- what is written down ---------------------------------------------------------


def test_every_decision_carries_its_inputs() -> None:
    run = Run()
    run.step(1, hesitant_step(1), page=HEAVY)
    run.end()

    for decision in run.decisions:
        row = decision.as_row()
        assert row["rules"] == "provisional"
        assert set(row) >= {"at", "step_index", "score", "level_before", "level",
                            "changed", "sent", "rule", "reason", "inputs"}
        assert set(row["inputs"]) >= {"level", "locked", "calm_streak",
                                      "changed_on_step", "thresholds"}
        assert 0.0 <= row["score"] <= 1.0
        assert row["reason"]
    start = run.decisions[0].as_row()
    assert start["inputs"]["page"]["overlays"] == 1
    waiting = [d.as_row() for d in run.decisions if d.at == "waiting"]
    assert waiting and all("telemetry" in row["inputs"] for row in waiting)


def test_a_decision_becomes_the_contract_message() -> None:
    rules = LevelRules()
    decision = rules.start_step(1, HEAVY)
    load = decision.load()
    assert (load.level, load.score) == (3, 1.0)
    assert load.reason == decision.reason


def test_telemetry_for_a_step_not_on_screen_changes_nothing() -> None:
    rules = LevelRules()
    rules.start_step(2, LIGHT)
    decision = rules.telemetry(sample(1, 30000, help_presses=3))
    assert (decision.rule, decision.send, rules.level) == ("stale", False, 2)


# --- the overflow guard (2026-09-25) ---------------------------------------------------
#
# The overlay drops a level when a step does not fit, and now says so with
# `level.override {by: "overflow"}`. The rules follow it, count it as the
# step's one change, and never let it become the person's lock.


def test_a_guard_move_is_followed_and_is_the_steps_one_change() -> None:
    rules = LevelRules()
    rules.start_step(1, LIGHT)
    decision = rules.override(1, locked=False, by="overflow")

    assert (decision.rule, decision.send, rules.level) == ("overflow", False, 1)
    # The same step does not also fold: the interface has moved once already.
    fold = rules.telemetry(sample(1, 16000))
    assert (fold.rule, rules.level) == ("once-per-step", 1)
    # The next step may.
    rules.start_step(2, LIGHT)
    rules.telemetry(sample(2, 16000))
    assert rules.level == 2


def test_a_guard_move_never_becomes_the_lock() -> None:
    rules = LevelRules()
    rules.override(2, locked=True)                       # the person's choice
    rules.start_step(1, LIGHT)
    rules.override(1, locked=True, by="overflow")        # the guard, under the lock

    assert (rules.level, rules.locked, rules.locked_level) == (1, True, 2)
    held = rules.telemetry(sample(1, 16000))
    assert held.rule == "locked" and "locked at 2" in held.reason
    # A new step is shown at the person's level again.
    rules.start_step(2, LIGHT)
    assert rules.level == 2


def test_a_guard_move_does_not_count_against_a_calm_run() -> None:
    """Not fitting is the screen's problem, not the person's."""
    run = Run()
    run.step(1, hesitant_step(1))
    run.step(2, calm_step(2))
    run.rules.override(2, locked=False, by="overflow")   # 3 -> 2, for fit
    run.step(3, calm_step(3))
    assert run.rules.calm_streak == 2


# --- the person's own level, from the welcome (2026-10-18) -------------------------


def started_at(level: int | None) -> Run:
    rules = LevelRules()
    rules.start_from(level)
    return Run(rules)


def test_a_task_starts_at_the_level_the_person_chose() -> None:
    for level in (1, 2, 3):
        run = started_at(level)
        run.step(1, calm_step(1))
        assert run.levels[1] == level
        assert [(d.at, d.level) for d in run.sent] == [("start", level)]


def test_the_start_says_it_is_the_persons_own_level() -> None:
    run = started_at(1)
    run.step(1, calm_step(1))
    assert "the person's own level, 1" in run.sent[0].reason


def test_a_heavy_page_still_starts_simplest_whatever_was_chosen() -> None:
    run = started_at(1)
    run.step(1, calm_step(1), page=HEAVY)
    assert run.levels[1] == 3


def test_calm_steps_come_back_to_the_persons_level_not_to_2() -> None:
    run = started_at(1)
    run.step(1, hesitant_step(1))
    assert run.levels[1] == 2  # one fold, from 1
    run.step(2, calm_step(2))
    run.step(3, calm_step(3))
    run.step(4, calm_step(4))
    assert run.levels[4] == 1


def test_a_person_who_chose_the_simplest_is_never_brought_back_to_2() -> None:
    run = started_at(3)
    for index in range(1, 6):
        run.step(index, calm_step(index))
    assert set(run.levels.values()) == {3}


def test_no_level_or_a_level_out_of_range_starts_at_2() -> None:
    for level in (None, 0, 4, "2", 2.0, True):
        run = started_at(level)  # type: ignore[arg-type]
        run.step(1, calm_step(1))
        assert run.levels[1] == 2


def test_the_level_cannot_be_changed_once_the_task_has_started() -> None:
    rules = LevelRules()
    rules.start_step(1, LIGHT)
    rules.start_from(1)
    assert (rules.baseline, rules.level) == (2, 2)


# --- with the trained model judging the page (2026-10-30) ---------------------------


#: The rating is 1 plus the text density, so a page's band can be read off it.
MODEL = PageModel(
    version="trained test", means=(0.0,) * 9, spreads=(1.0,) * 9,
    coefficients=(0, 0, 0, 1.0, 0, 0, 0, 0, 0), intercept=1.0, calm=2.45, heavy=2.9)
CALM = replace(LIGHT, text_density=0.5)  # 1.5
MIDDLE = replace(LIGHT, text_density=1.6)  # 2.6
#: Plain to the rules, with none of their signs, and heavy to the model.
HEAVY_TO_THE_MODEL = replace(LIGHT, text_density=2.2)  # 3.2
#: Two of the rules' signs, and calm to the model.
HEAVY_TO_THE_RULES = replace(LIGHT, controls=200, overlays=1, text_density=0.5)


def judged(level: int | None = None) -> Run:
    rules = LevelRules(page_model=MODEL)
    rules.start_from(level)
    return Run(rules)


def test_the_model_starts_a_heavy_page_at_3_where_the_rules_would_not() -> None:
    assert LevelRules().start_step(1, HEAVY_TO_THE_MODEL).level == 2
    decision = LevelRules(page_model=MODEL).start_step(1, HEAVY_TO_THE_MODEL)
    assert decision.level == 3
    assert decision.send is True
    assert decision.reason.startswith("3.2 of 5")


def test_the_model_overrules_the_rules_signs() -> None:
    assert LevelRules().start_step(1, HEAVY_TO_THE_RULES).level == 3
    assert LevelRules(page_model=MODEL).start_step(1, HEAVY_TO_THE_RULES).level == 2


def test_a_calm_page_does_not_bring_more_detail_than_the_person_has_said() -> None:
    """The model's level is 1. More detail is something a person chooses."""
    assert LevelRules(page_model=MODEL).start_step(1, CALM).level == 2


def test_a_person_who_chose_more_detail_gets_it_on_a_calm_page() -> None:
    run = judged(1)
    run.step(1, calm_step(1), CALM)
    assert run.levels[1] == 1


def test_a_page_can_start_someone_simpler_than_the_level_they_chose() -> None:
    for level, page, expected in ((1, MIDDLE, 2), (1, HEAVY_TO_THE_MODEL, 3),
                                  (2, HEAVY_TO_THE_MODEL, 3)):
        run = judged(level)
        run.step(1, calm_step(1), page)
        assert run.levels[1] == expected, (level, page.text_density)


def test_a_page_never_starts_someone_with_more_than_the_level_they_chose() -> None:
    for page in (CALM, MIDDLE, HEAVY_TO_THE_MODEL):
        run = judged(3)
        run.step(1, calm_step(1), page)
        assert run.levels[1] == 3


def test_their_own_level_is_named_when_it_is_what_decided() -> None:
    assert "the person's own level, 3" in judged(3).rules.start_step(1, CALM).reason


def test_hesitation_still_folds_a_step_the_model_started() -> None:
    run = judged()
    run.step(1, hesitant_step(1), MIDDLE)
    assert run.levels[1] == 3


def test_calm_steps_still_bring_a_heavy_start_back_to_the_persons_own_level() -> None:
    """One level for every two calm steps, however heavy the first page was."""
    for level, back in ((None, 2), (1, 1)):
        run = judged(level)
        for index in range(1, 6):
            run.step(index, calm_step(index), HEAVY_TO_THE_MODEL)
        assert run.levels[1] == 3 and run.levels[3] == 2 and run.levels[5] == back


def test_a_lock_holds_against_the_model() -> None:
    rules = LevelRules(page_model=MODEL)
    rules.override(1, True)
    decision = rules.start_step(1, HEAVY_TO_THE_MODEL)
    assert decision.level == 1 and decision.send is False
    assert "would start at 3" in decision.reason


def test_a_page_with_no_features_starts_where_the_person_is() -> None:
    decision = LevelRules(page_model=MODEL).start_step(1, None)
    assert decision.level == 2


def test_the_score_sent_is_the_models_and_a_strong_signal_still_beats_it() -> None:
    rules = LevelRules(page_model=MODEL)
    assert rules.start_step(1, MIDDLE).score == 0.4
    assert rules.telemetry(sample(1, 15000)).score == 1.0


def test_with_no_model_every_decision_is_what_the_rules_alone_decided() -> None:
    """The fallback is the old behaviour, row for row: nothing is judged."""
    for page in (LIGHT, HEAVY, None):
        plain, none = LevelRules(), LevelRules(page_model=None)
        one, two = plain.start_step(1, page), none.start_step(1, page)
        assert one.as_row() == two.as_row()
        assert one.judged_by == RULES_VERSION


def test_every_decision_says_who_judged_the_page() -> None:
    run = judged()
    run.step(1, hesitant_step(1), MIDDLE)
    run.end()
    rows = [d.as_row() for d in run.decisions]
    assert {row["judged_by"] for row in rows} == {"trained test"}
    assert {row["rules"] for row in rows} == {RULES_VERSION}


def test_a_step_row_holds_the_judgement_and_what_the_rules_would_have_said() -> None:
    """So that the two can be compared on every real run from now on."""
    inputs = LevelRules(page_model=MODEL).start_step(1, HEAVY).inputs
    assert inputs["judged"]["level"] == 3 and inputs["judged"]["reasons"]
    assert inputs["heavy_signs"]
