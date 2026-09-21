"""What a typed goal is asking for, decided before anything is allowed to run.

Until 2026-09-21 the backend's `SIMBA_FLOW` chose the task and the typed goal
was only its label. Typing "hello" into a backend started as `billing` opened
the billing site and began on somebody's bill. That breaks the rule this
module exists for: **nothing starts that the person did not ask for.**

A goal goes one of four ways:

  * `flow` — it is one of the things SIMBA can do. Run that flow, with the
    goal as typed.
  * `greeting` — small talk, or nothing at all. Say hello and offer what can
    be done.
  * `unsupported` — a real request SIMBA cannot do. Say so, and offer what
    can be done.
  * `clarify` — it could be two of the flows. Ask which, with both as buttons.

**The model decides when it is there; keywords decide when it is not.** One
call to the configured provider, with a short timeout and no rate-limit
waiting: a classification is not worth a minute of a person's time. No key,
no quota, a slow answer or an answer outside the list all fall back to the
keyword classifier, so routing works offline and on demo day.

**One floor sits under both.** A goal made only of small talk is a greeting
whatever the model says. The model is allowed to be wrong about which flow;
it is not allowed to start one from "hello".

No words live here. A route says *what kind* of reply and *which flows* to
offer; the overlay writes the sentences from `copy.ts`, where every other
sentence the person reads is kept and checked.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ValidationError

#: The flows a person can reach by asking. `stubborn` is a measurement rig and
#: deliberately not here: nothing a person types should land on a page built
#: to fail.
ROUTABLE: tuple[str, ...] = ("registration", "billing", "railways")

#: Seconds the model gets before the keywords decide instead. Long enough for
#: a small model on a normal connection; short enough that a dead one is not
#: noticed as a pause. Module-level so a test can shorten it.
MODEL_TIMEOUT_S = 8.0

RouteKind = Literal["flow", "greeting", "unsupported", "clarify"]


@dataclass(frozen=True)
class Route:
    """Where a goal goes, and how that was decided."""

    kind: RouteKind
    #: The flow to run. Set only when `kind` is `flow`.
    flow: str | None
    #: What to offer. The flow itself for `flow`, the candidates for
    #: `clarify`, everything for `greeting` and `unsupported`.
    flows: tuple[str, ...]
    #: `model` or `keywords` — which one decided. Logged, never shown.
    via: str


# --- keywords ----------------------------------------------------------------
#
# Deliberately small and deliberately literal. These are the fallback, and a
# fallback that guesses cleverly is a fallback that starts the wrong task. A
# word goes in a list only if it points at one flow and not at anything a
# person would ask for that SIMBA cannot do: "book" is in no list, because
# "book a flight" and "book a hotel" are exactly the requests to decline, and
# "ticket" is in none either, for the same reason.

FLOW_WORDS: dict[str, frozenset[str]] = {
    "registration": frozenset({
        "register", "registration", "enrol", "enroll", "enrolment", "enrollment",
        "course", "courses", "class", "classes", "module", "semester", "cs",
        "university", "timetabled", "elective",
    }),
    "billing": frozenset({
        "bill", "bills", "electricity", "electric", "power", "pay", "payment",
        "owe", "due", "amount", "reference", "meter", "utility", "fee", "fees",
    }),
    "railways": frozenset({
        "train", "trains", "railway", "railways", "rail", "station", "stations",
        "timings",
    }),
}

#: Place names count, but for half. "Lahore to Karachi" is two of them and a
#: railways request; "a hotel in Lahore" is one and is not. Found by the test
#: that expected the hotel to be declined and watched it open the train site.
WEAK_WORDS: dict[str, frozenset[str]] = {
    "railways": frozenset({
        "karachi", "lahore", "rawalpindi", "islamabad", "multan", "peshawar",
        "quetta", "faisalabad", "hyderabad", "sukkur",
    }),
}

#: Words that name something SIMBA does not do. One of these with only weak
#: evidence for a flow is a request to decline, not a flow to guess at.
ELSEWHERE = frozenset({
    "flight", "flights", "fly", "plane", "airline", "airport", "hotel", "hotels",
    "taxi", "uber", "careem", "bus", "pizza", "food", "restaurant", "weather",
    "email", "mail", "message", "call", "phone", "movie", "cinema", "shop",
    "shopping", "buy", "doctor", "appointment",
})

#: Words that carry no request of their own. A goal made only of these, plus
#: filler, is small talk.
SMALL_TALK = frozenset({
    "hello", "hi", "hey", "hiya", "hullo", "salaam", "salam", "assalamualaikum",
    "thanks", "thank", "thankyou", "ta", "cheers", "bye", "goodbye", "ok", "okay",
    "good", "morning", "afternoon", "evening", "night", "how", "are", "you",
    "doing", "there", "so", "much", "very", "yes", "no", "please", "sup", "whats",
    "up", "nice", "great", "cool",
})

_WORD = re.compile(r"[a-z]+")


def _words(goal: str) -> list[str]:
    return _WORD.findall(goal.lower())


def is_small_talk(goal: str) -> bool:
    """Nothing asked for: empty, or only greetings and pleasantries."""
    words = _words(goal)
    return all(word in SMALL_TALK for word in words)


def by_keywords(goal: str) -> Route:
    """The offline classifier. Counts which flow's words appear.

    A clear winner is that flow. A tie between two or more is a question —
    "pay for my course" names the bill site and the course site equally, and
    guessing is how the wrong task starts. No flow words at all is either
    small talk or a request SIMBA cannot do.
    """
    if is_small_talk(goal):
        return Route("greeting", None, ROUTABLE, "keywords")

    words = _words(goal)
    strong = {
        flow: sum(1 for word in words if word in vocabulary)
        for flow, vocabulary in FLOW_WORDS.items()
    }
    scores = {
        flow: strong[flow] + 0.5 * sum(
            1 for word in words if word in WEAK_WORDS.get(flow, ()))
        for flow in FLOW_WORDS
    }
    best = max(scores.values())
    # A flow needs one strong word or two weak ones, and anything naming a
    # thing SIMBA does not do needs a strong word to be overruled.
    vetoed = any(word in ELSEWHERE for word in words) and max(strong.values()) == 0
    if best < 1 or vetoed:
        return Route("unsupported", None, ROUTABLE, "keywords")

    leaders = tuple(flow for flow in ROUTABLE if scores[flow] == best)
    if len(leaders) > 1:
        return Route("clarify", None, leaders, "keywords")
    return Route("flow", leaders[0], leaders, "keywords")


# --- the model ---------------------------------------------------------------


class RouteChoice(BaseModel):
    """What the model is allowed to answer. Validated like every other reply."""

    route: str
    options: list[str]


#: The JSON schema a provider pins the answer to, where it can.
ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "route": {
            "type": "string",
            "enum": [*ROUTABLE, "greeting", "unsupported", "ambiguous"],
        },
        "options": {"type": "array", "items": {"type": "string", "enum": list(ROUTABLE)}},
    },
    "required": ["route", "options"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You sort one request typed by a person into what a helper app can do for them.
The app can do exactly three things:

- registration: register for a university course, such as CS-401.
- billing: look up an electricity bill or the amount due on it.
- railways: find trains between two cities in Pakistan on a date.

Answer with JSON: {"route": ..., "options": [...]}.

- If the request is one of the three, route is that name and options is [].
- If it is only a greeting, thanks or small talk, route is "greeting".
- If it is a real request for anything else, route is "unsupported".
- If it could fairly be two of the three and you cannot tell which, route is
  "ambiguous" and options lists those two.

Never choose one of the three unless the person asked for it.
"""


class Classifier(Protocol):
    async def choose_route(self, system_prompt: str, goal: str) -> RouteChoice: ...


def use_model() -> bool:
    """`SIMBA_ROUTER=keywords` never calls a model; anything else may."""
    return os.environ.get("SIMBA_ROUTER", "model").strip().lower() != "keywords"


def configured_classifier() -> Classifier | None:
    """The configured provider, or None if there is none to ask.

    Shared by the real backend and the mock, so a demo routes exactly as the
    product does. No key is not an error: it is why the keywords exist.
    """
    if not use_model():
        return None
    try:
        from backend.orchestrator.llm import provider_from_env

        return provider_from_env()
    except Exception as error:  # noqa: BLE001 - no key, unknown provider, no SDK
        logging.getLogger("simba.router").info("routing by keywords: %s", error)
        return None


def _from_model(choice: RouteChoice) -> Route | None:
    """The model's answer as a route, or None if it is not a usable one."""
    if choice.route in ROUTABLE:
        return Route("flow", choice.route, (choice.route,), "model")
    if choice.route == "greeting":
        return Route("greeting", None, ROUTABLE, "model")
    if choice.route == "unsupported":
        return Route("unsupported", None, ROUTABLE, "model")
    if choice.route == "ambiguous":
        options = tuple(flow for flow in ROUTABLE if flow in choice.options)
        # The model could not tell. A question with one answer is not a
        # question, and running the one flow it half-named is a guess — so
        # ask across everything instead. Falling through to the keywords here
        # was tried: they read "fees" and started the bill.
        return Route("clarify", None, options if len(options) >= 2 else ROUTABLE, "model")
    return None


async def route(goal: str, model: Classifier | None = None) -> Route:
    """Where a goal goes. The model if it answers usably, keywords otherwise."""
    # The floor, before anything else is asked. Cheap, local, and the one
    # rule that must hold even when the model is confidently wrong.
    if is_small_talk(goal):
        return Route("greeting", None, ROUTABLE, "keywords")

    if model is not None:
        try:
            choice = await asyncio.wait_for(
                model.choose_route(SYSTEM_PROMPT, goal.strip()), MODEL_TIMEOUT_S
            )
            decided = _from_model(choice)
            if decided is not None:
                return decided
        except (asyncio.TimeoutError, ValidationError, Exception):  # noqa: BLE001
            # No key, no quota, no network, a malformed answer, or too slow.
            # All of them mean the same thing here: the keywords decide.
            pass
    return by_keywords(goal)
