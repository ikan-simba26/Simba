"""A page that offers more than one way to pay (2026-11-16, Raham: "it should
adapt to the website"): the person chooses, from the page's own words; a goal
that already names a way is not asked; one way only is not a choice."""

import asyncio

from backend.orchestrator import voice
from backend.orchestrator.llm import Action
from backend.orchestrator.llm_loop import OpenGoalPlanner
from backend.orchestrator.loop import Task
from backend.orchestrator.plan import About
from backend.perception.serializer import Element


class Model:
    label = "test"

    def __init__(self, element_id: int) -> None:
        self.element_id = element_id

    async def decide(self, system_prompt, page, goal, feedback=None, history=None):
        return Action(action="click", element_id=self.element_id, reasoning="Paying.")


def radio(id: int, label: str) -> Element:
    return Element(id=id, role="radio", label=label, type="click", tag="input", input_type="radio")


def planner(goal: str, element_id: int) -> OpenGoalPlanner:
    task = Task(goal=goal, estimated_steps=5, success=None, about=About())
    return OpenGoalPlanner(Model(element_id), task, ask_answer=False)


CHECKOUT = [radio(1, "Cash on delivery"), radio(2, "Pay online by card")]


def test_two_ways_to_pay_are_asked_not_chosen() -> None:
    move = asyncio.run(planner("Order the kettle", 1).next_move(CHECKOUT, [], None))
    assert move.question and move.instruction == voice.PAY_HOW
    labels = [a.label for a in move.actions if a.id.startswith(voice.PAY_ID_PREFIX)]
    assert labels == ["Cash on delivery", "Pay online by card"]


def test_the_way_the_person_chose_is_the_one_pressed() -> None:
    chooser = planner("Order the kettle", 1)
    asked = asyncio.run(chooser.next_move(CHECKOUT, [], None))
    online = next(a.id for a in asked.actions if a.label == "Pay online by card")
    chooser.answered(online, {})
    move = asyncio.run(chooser.next_move(CHECKOUT, [], None))
    assert not move.question and move.operations[0].element_id == 2


def test_a_goal_that_names_the_way_is_not_asked() -> None:
    move = asyncio.run(
        planner("Order the kettle, cash on delivery", 1).next_move(CHECKOUT, [], None))
    assert not move.question and move.operations[0].element_id == 1


def test_one_way_only_is_not_a_choice() -> None:
    move = asyncio.run(planner("Order the kettle", 1).next_move(CHECKOUT[:1], [], None))
    assert not move.question and move.operations[0].element_id == 1
