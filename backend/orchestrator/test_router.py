"""What a typed goal turns into, before anything is allowed to run.

Until 2026-09-21 `SIMBA_FLOW` chose the task and the typed goal was only its
label, so typing "hello" into a backend started as `billing` opened the
billing site and began paying a bill. The router is the fix, and the rule it
exists to keep is the one that failure broke: **nothing starts that the
person did not ask for.**
"""

import asyncio

import pytest

from backend.orchestrator.router import (
    ROUTABLE,
    Route,
    RouteChoice,
    by_keywords,
    route,
)


def keywords(goal: str) -> Route:
    return by_keywords(goal)


# --- the five the task named -------------------------------------------------


def test_hello_is_a_greeting_and_starts_nothing() -> None:
    found = keywords("hello")

    assert found.kind == "greeting"
    assert found.flow is None
    # A greeting offers everything that can be done.
    assert set(found.flows) == set(ROUTABLE)


def test_pay_my_bill_is_billing() -> None:
    found = keywords("pay my bill")

    assert found.kind == "flow"
    assert found.flow == "billing"


def test_trains_to_karachi_is_railways() -> None:
    found = keywords("trains to Karachi")

    assert found.kind == "flow"
    assert found.flow == "railways"


def test_book_a_flight_is_something_i_cannot_do() -> None:
    found = keywords("book a flight")

    assert found.kind == "unsupported"
    assert found.flow is None
    assert set(found.flows) == set(ROUTABLE)


def test_something_ambiguous_is_asked_about_not_guessed() -> None:
    """Paying for a course: the bill site or the registration site."""
    found = keywords("I need to pay for my course")

    assert found.kind == "clarify"
    assert found.flow is None
    assert set(found.flows) == {"billing", "registration"}


# --- and the edges of each -----------------------------------------------------


@pytest.mark.parametrize("goal", [
    "hi", "Hi!", "hey there", "thanks", "thank you", "Thank you so much.",
    "good morning", "how are you?", "ok", "bye",
])
def test_small_talk_is_a_greeting(goal: str) -> None:
    assert keywords(goal).kind == "greeting", goal


@pytest.mark.parametrize("goal", ["", "   ", "\n"])
def test_an_empty_goal_starts_nothing(goal: str) -> None:
    """The contract used to fall back to the configured flow here. An empty
    box is nobody asking for anything."""
    assert keywords(goal).kind == "greeting"


@pytest.mark.parametrize("goal,flow", [
    ("Register for CS-401", "registration"),
    ("Register for the course CS-401.", "registration"),
    ("enrol me in a class", "registration"),
    ("Find the amount due for reference number 04141234567890.", "billing"),
    ("how much is my electricity bill", "billing"),
    ("Check my electricity bill", "billing"),
    ("Find trains from Lahore to Karachi on 15 October 2026.", "railways"),
    ("train timings to Lahore", "railways"),
    ("Lahore to Karachi tomorrow", "railways"),
])
def test_the_flows_own_goals_route_to_themselves(goal: str, flow: str) -> None:
    """Every goal a plan, a card or a test already sends still lands where it did."""
    found = keywords(goal)
    assert (found.kind, found.flow) == ("flow", flow), (goal, found)


@pytest.mark.parametrize("goal", [
    "book a flight", "order a pizza", "what's the weather", "send an email to Ali",
    "book a hotel in Lahore",
])
def test_real_requests_outside_the_flows_are_declined(goal: str) -> None:
    assert keywords(goal).kind == "unsupported", goal


@pytest.mark.parametrize("goal,flows", [
    # The case that ran billing when the model timed out on 2026-09-21: two
    # bill words beat one class word, and only one of two requests started.
    ("I have a payment due and a class to sign up for", {"billing", "registration"}),
    ("pay my electricity bill and then find me a train", {"billing", "railways"}),
    ("register for CS-401 and check the train times", {"registration", "railways"}),
    ("sort out my university fee", {"billing", "registration"}),
])
def test_strong_words_for_two_flows_ask_which_rather_than_run_one(
    goal: str, flows: set[str]
) -> None:
    """A count is not a choice. Two flows named outright is a question."""
    found = keywords(goal)

    assert found.kind == "clarify", (goal, found)
    assert set(found.flows) == flows


def test_a_place_name_alone_does_not_make_a_second_flow() -> None:
    """Weak words still only add up; they never force a question on their own."""
    found = keywords("check my electricity bill before I go to Lahore")

    assert (found.kind, found.flow) == ("flow", "billing")


def test_hello_with_a_request_is_the_request() -> None:
    """A greeting in front of a request does not swallow it."""
    found = keywords("hi, can you check my electricity bill")
    assert (found.kind, found.flow) == ("flow", "billing")


# --- the model, and what happens when it is not there -------------------------


class FakeModel:
    """Stands in for a provider's `choose_route`. Records what it was asked."""

    def __init__(self, answer: object = None, error: Exception | None = None) -> None:
        self.answer = answer
        self.error = error
        self.asked: list[str] = []

    async def choose_route(self, system_prompt: str, goal: str) -> RouteChoice:
        self.asked.append(goal)
        if self.error is not None:
            raise self.error
        return RouteChoice.model_validate(self.answer)


def routed(goal: str, model) -> Route:
    return asyncio.run(route(goal, model=model))


def test_the_model_is_asked_once_and_believed() -> None:
    model = FakeModel({"route": "railways", "options": []})

    found = routed("I want to go to Karachi next week", model)

    assert model.asked == ["I want to go to Karachi next week"]
    assert (found.kind, found.flow, found.via) == ("flow", "railways", "model")


def test_the_model_can_ask_a_question() -> None:
    model = FakeModel({"route": "ambiguous", "options": ["billing", "registration"]})

    found = routed("sort out my fees", model)

    assert found.kind == "clarify"
    assert set(found.flows) == {"billing", "registration"}


def test_an_ambiguous_answer_with_one_option_runs_nothing() -> None:
    """The model could not tell, so nothing runs — not even the one it named."""
    model = FakeModel({"route": "ambiguous", "options": ["billing"]})

    found = routed("sort out my fees", model)

    assert found.kind == "clarify"
    assert set(found.flows) == set(ROUTABLE)


def test_no_key_falls_back_to_keywords() -> None:
    from backend.orchestrator.llm import LLMError

    found = routed("pay my bill", FakeModel(error=LLMError("ANTHROPIC_API_KEY is not set")))

    assert (found.kind, found.flow, found.via) == ("flow", "billing", "keywords")


def test_no_quota_falls_back_to_keywords() -> None:
    found = routed("trains to Karachi", FakeModel(error=RuntimeError("429 quota exceeded")))

    assert (found.kind, found.flow, found.via) == ("flow", "railways", "keywords")


def test_a_model_answer_outside_the_flows_falls_back() -> None:
    found = routed("pay my bill", FakeModel({"route": "flights", "options": []}))

    assert (found.flow, found.via) == ("billing", "keywords")


def test_no_model_at_all_is_keywords() -> None:
    found = routed("book a flight", None)

    assert (found.kind, found.via) == ("unsupported", "keywords")


def test_the_model_cannot_start_a_task_from_small_talk() -> None:
    """The floor under everything: "hello" never runs a flow, whatever says so."""
    found = routed("hello", FakeModel({"route": "billing", "options": []}))

    assert found.kind == "greeting"
    assert found.flow is None


def test_a_slow_model_is_not_waited_for(monkeypatch) -> None:
    """A classification is one call; a person does not wait a minute for it."""
    from backend.orchestrator import router

    monkeypatch.setattr(router, "MODEL_TIMEOUT_S", 0.05)

    class Slow(FakeModel):
        async def choose_route(self, system_prompt: str, goal: str) -> RouteChoice:
            await asyncio.sleep(1)
            return RouteChoice(route="registration", options=[])

    found = routed("pay my bill", Slow())

    assert (found.flow, found.via) == ("billing", "keywords")
