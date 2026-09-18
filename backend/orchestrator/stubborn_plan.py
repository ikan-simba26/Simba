"""A flow whose first move fails on purpose, so recovery can be measured.

The loop absorbs a first failure: it emits `step.failed`, hands the reason to
the planner as a setback, and lets it choose again. Whether a planner actually
*uses* that setback has never been measured on a run. It could not be: the
replicas always worked, and a live site cannot be asked to fail on demand, so
two successful runs told us nothing (EVALUATION.md, 2026-09-17j).

The registration replica now serves `/stubborn`: a "Continue" button with no
form and no handler, and a link that reaches the course list. The button is
honest in every way perception can see — named, enabled, visible, uncovered —
and pressing it changes nothing, so the move fails both strategies and the
run carries on with a setback in hand.

Two planners, two questions:

  * `STUBBORN_PLAN` is the deterministic arm. Step 1 presses Continue and
    fails; step 2 takes the long way and completes. It proves the rig works
    and that a run survives a failed step, with no model involved.
  * `LLMPlanner` is the experiment. Its first choice is its own; what matters
    is what it does on the second, having been told the first did nothing.
    `SIMBA_SETBACK_PLACEMENT` decides whether it was told above the element
    list or after it.

Nothing here is irreversible and nothing leaves the machine: it is a local
replica page with a dead button on it.
"""

from backend.orchestrator.loop import Task
from backend.orchestrator.plan import About, Expectation, Operation, PlanStep, Target
from backend.orchestrator.voice import actions

STUBBORN_URL = "http://127.0.0.1:5000/stubborn"

GOAL = "Open the course list."

STUBBORN_TASK = Task(
    goal=GOAL,
    estimated_steps=2,
    # The course list, whichever way the planner got there.
    success=Expectation(url_contains="/courses"),
    # Nothing to hold and nothing to find: this flow is about recovery.
    about=About(),
)

STUBBORN_PLAN: list[PlanStep] = [
    PlanStep(
        instruction="Let me try the quick way in.",
        detail="The page offers this first.",
        actions=actions("Try Continue"),
        # Dead. The click lands, the page does not change, and both
        # strategies fail — the second is a JS click on the same dead button.
        operations=[Operation("click", Target("button", "Continue"))],
        expect=Expectation(url_contains="/courses"),
    ),
    PlanStep(
        instruction="That did nothing. Let me go round the other way.",
        detail="Through the registrar's own page.",
        actions=actions("Take the long way"),
        operations=[Operation("click", Target("link", "Take the long way round"))],
        expect=Expectation(url_contains="/courses"),
    ),
]
