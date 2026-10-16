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

from dataclasses import replace

from backend.orchestrator.loop import Task
from backend.orchestrator.plan import (
    About,
    Answer,
    Expectation,
    Operation,
    PlanStep,
    Shown,
    Target,
)
from backend.orchestrator import voice
from backend.orchestrator.voice import actions
from shared.schema import StepField

REFERENCE = "04141234567890"
GOAL = "Find the amount due for reference number 04141234567890."


def bill_task(reference: str) -> Task:
    """The billing task for one reference number — the person's own."""
    return Task(
        goal=f"Find the amount due for reference number {reference}.",
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
        # field left to check it in. What can be checked is what the site says
        # back: the bill it shows carries a reference number of its own, and it
        # has to be the one that was asked about. See `Shown`.
        about=About(
            finds=(
                Answer("Your bill", reads="P/WITHIN"),
                Answer("Due", reads="DUE DT"),
            ),
            shows=(Shown(reads="REF NO", says=reference),),
        ),
        explain=voice.explain_bill,
        scope=voice.ONLY_LOOKED_AT_BILL,
    )


def billing_plan(reference: str) -> list[PlanStep]:
    """The billing plan for one reference number."""
    return [
        PlanStep(
            # Asked, Yes or No (2026-10-16): consent on someone else's site
            # is the person's to give. No leaves the banner as it is.
            instruction=voice.ASK_COOKIES,
            detail="",
            actions=voice.yes_or_no(),
            operations=[Operation("click", Target("button", "Accept all cookies"))],
            expect=Expectation(label_gone="Accept all cookies"),
            stage=1,
        ),
        PlanStep(
            instruction="Let me look up your bill.",
            detail="Using the 14-digit reference number from your bill.",
            fields=[
                StepField(id="reference", label="Reference No.", type="text", value=reference),
            ],
            actions=actions("Check the bill"),
            operations=[
                Operation("fill", Target("textbox", "Reference No."), value=reference),
                Operation("click", Target("button", "Check Bill")),
            ],
            expect=Expectation(url_contains="/bill"),
            stage=1,
            # A lookup with the number the person gave: safe to run.
            safe=True,
            doing=voice.DOING_LOOKUP,
        ),
        PlanStep(
            instruction="Now I'll open the full bill.",
            detail="This shows what makes up the amount due.",
            actions=actions("Show me the breakdown"),
            operations=[Operation("click", Target("link", "View full bill detail"))],
            expect=Expectation(url_contains="/bill/detail", title_contains="Bill Detail"),
            stage=1,
            safe=True,
            doing=voice.DOING_FULL_BILL,
        ),
    ]


def person_billing_plan(reference: str) -> list[PlanStep]:
    """A person's bill (2026-10-16): the cookie question and the lookup, and
    no more. The run used to open the full bill afterwards, a page where
    neither the amount nor the due date it reports is shown, so nothing could
    be checked or shown there before closing. It ends on the results page."""
    return billing_plan(reference)[:2]


def person_bill_task(reference: str) -> Task:
    """The task for `person_billing_plan`: done on the results page."""
    return replace(bill_task(reference), estimated_steps=2,
                   success=Expectation(url_contains="/bill",
                                       title_contains="Bill Enquiry Result"))


# The worked example, which every recorded billing number was measured on. A
# person's request runs `bill_task` and `billing_plan` with their own number.
BILLING_TASK = bill_task(REFERENCE)
BILLING_PLAN: list[PlanStep] = billing_plan(REFERENCE)
