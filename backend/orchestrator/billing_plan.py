"""The hardcoded billing plan.

The second site, so the loop, verification and recovery get exercised on
something that is not the page they were written against. Nothing here is
billing-specific machinery — it is the same PlanStep, Operation and
Expectation the registration plan uses.

Note what this plan cannot express: the goal is to *read* the amount due, and
perception only serializes interactive elements, so no step can assert the
amount was found. The success condition below therefore checks that the
detail page was reached, which is where the amount is stated — a proxy for
the real goal. See EVALUATION.md, 2026-09-06.
"""

from backend.orchestrator.loop import Task
from backend.orchestrator.plan import About, Answer, Expectation, Operation, PlanStep, Target
from shared.schema import StepAction, StepField

REFERENCE = "04141234567890"
GOAL = "Find the amount due for reference number 04141234567890."


def _confirm(label: str) -> list[StepAction]:
    return [
        StepAction(id="confirm", label=label, kind="primary"),
        StepAction(id="cancel", label="Not now", kind="secondary"),
    ]


BILLING_TASK = Task(
    goal=GOAL,
    estimated_steps=3,
    success=Expectation(url_contains="/bill/detail", title_contains="Bill Detail"),
    # What the goal is actually asking, and what to call it on screen. The
    # page's own heading for the amount is `P/WITHIN`, which means nothing
    # outside a billing department.
    #
    # Both are read off the results page and remembered; the run then opens
    # the detail page, where neither column exists. See `findings_in`.
    #
    # Nothing in `holds`: the goal names a reference number, but it is typed
    # on the lookup page and the run ends two pages later, where there is no
    # field left to check it in. See `About`.
    about=About(
        finds=(
            Answer("Your bill", reads="P/WITHIN"),
            Answer("Due", reads="DUE DT"),
        ),
    ),
)

BILLING_PLAN: list[PlanStep] = [
    PlanStep(
        instruction="The site is asking about cookies. I’ll say yes.",
        detail="The site is asking about cookies before anything else.",
        actions=_confirm("Accept cookies"),
        operations=[Operation("click", Target("button", "Accept all cookies"))],
        expect=Expectation(label_gone="Accept all cookies"),
    ),
    PlanStep(
        instruction="Let me look up your bill.",
        detail="Using the 14-digit reference number from your bill.",
        fields=[
            StepField(id="reference", label="Reference No.", type="text", value=REFERENCE),
        ],
        actions=_confirm("Check the bill"),
        operations=[
            Operation("fill", Target("textbox", "Reference No."), value=REFERENCE),
            Operation("click", Target("button", "Check Bill")),
        ],
        expect=Expectation(url_contains="/bill"),
    ),
    PlanStep(
        instruction="Now I’ll open the full bill.",
        detail="This shows what makes up the amount due.",
        actions=_confirm("Show me the breakdown"),
        operations=[Operation("click", Target("link", "View full bill detail"))],
        expect=Expectation(url_contains="/bill/detail", title_contains="Bill Detail"),
    ),
]
