"""Every answer about a journey is checked before anything on the site is done.

On 2026-10-06, run on `railways-local`, SIMBA did not ask where the person
was going: the home screen's train card sends "Find trains from Lahore to
Karachi", so the card's own words named both ends. And where it did ask, a
station was whatever was typed, held to the site only mid-run — after the box
had been typed into — and a journey from Lahore Cantt to Lahore Cantt, or a
day in the calendar that does not exist, was never noticed as one.

Now (`details.TripBrief`):

  * the site's own station list is read first, without touching the page,
    and the station questions offer it to choose from;
  * a station not on it is met with the nearest names that are;
  * a city with two stations is asked about before anything is typed;
  * a journey that starts where it ends is asked about again;
  * a day that has gone, that is further ahead than can be looked up, or that
    is not in the calendar, is said to be so, kindly, and asked again;
  * the journey is read back once, and only a yes starts the run.

The first half needs no browser: a page that holds a list is all `prepare`
reads. The second half runs the real loop on the railways replica in real
Chromium, and the last runs the real app over its websocket with a model that
has no quota, which is how it is launched by default.

Today is fixed at Tuesday 2026-10-06 in the first half.
"""

import asyncio
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import websockets
from playwright.async_api import async_playwright

from backend.orchestrator import details, voice
from backend.orchestrator.details import (
    MAX_TRIES,
    DetailsChoice,
    TripBrief,
    Understood,
    match_station,
    read_day,
    understand,
)
from backend.orchestrator.loop import run_brief
from backend.orchestrator.railways_plan import TripPlanner
from backend.orchestrator.test_asking import ScriptedConnection
from backend.orchestrator.test_orchestrator import _wait_for
from backend.orchestrator.voice import CANCEL_ID, CHOICE_PREFIX, TYPED_ANSWERS

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]

TODAY = date(2026, 10, 6)
TOMORROW = date(2026, 10, 7)

# The live list's shape: capitals, a dot after JN., one city with two stations.
STATIONS = [
    "LAHORE JN.", "LAHORE CANTT", "KARACHI CANTT", "KARACHI CITY", "RAWALPINDI",
    "MULTAN CANTT", "HYDERABAD JN.", "SUKKUR", "QUETTA", "KOT LAKHPAT",
    "KOT RADHA KISHEN", "KOTRI JN.", "KOTADUJN.", "KOT NAJIBULLAH", "KOTSULTAN",
]


def run(coroutine):
    """On its own thread, for the reason `test_details.read` gives: a sync
    Playwright session from another module holds a loop on this one."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def choice(index: int) -> tuple[str, dict]:
    return f"{CHOICE_PREFIX}{index}", {}


class ListedPage:
    """All `prepare` looks at: a page holding one list of choices."""

    def __init__(self, names: list[str]) -> None:
        self.names = names
        self.evaluated = 0

    async def evaluate(self, script: str):  # noqa: ARG002
        self.evaluated += 1
        return [list(self.names)]


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch) -> None:
    monkeypatch.setattr(details, "STATION_LIST_POLL_S", 0.0)


def brief(goal: str = "I need a train", stations: list[str] | None = STATIONS,
          today: date = TODAY, **known) -> TripBrief:
    """A trip brief that has read `stations` off the page, as the app's would."""
    made = TripBrief(goal, Understood(**known), today=today)
    if stations is not None:
        run(made.prepare(ListedPage(stations)))
    return made


def asked(made: TripBrief) -> str:
    """What the question leads with: what was wrong with the last answer, if
    anything was (`note`, since 2026-10-14), or else the question itself."""
    question = made.question()
    assert question is not None
    return question.note or question.instruction


def labels(made: TripBrief) -> list[str]:
    question = made.question()
    assert question is not None
    return [action.label for action in question.actions]


def to_the_day(made: TripBrief) -> None:
    """Past both stations, with the day question's "Pick another day" pressed."""
    made.question()
    made.answered("confirm", {"origin": "Rawalpindi"})
    made.question()
    made.answered("confirm", {"destination": "Sukkur"})
    made.question()
    made.answered(*choice(2))


# --- the stations come from the site ------------------------------------------


def test_a_station_question_offers_the_sites_own_list() -> None:
    question = brief().question()

    assert question is not None and question.instruction == voice.ASK_FROM
    [field] = question.fields
    assert (field.id, field.type, field.options) == ("origin", "choice", STATIONS)
    assert [a.label for a in question.actions] == [voice.USE_STATION, voice.STOP]


def test_a_station_chosen_from_the_list_is_taken_as_the_site_names_it() -> None:
    """The overlay sends the name as it showed it; the site's own is kept."""
    made = brief()
    made.question()

    made.answered("confirm", {"origin": "Lahore Jn."})

    assert made.chosen["origin"] == "LAHORE JN."
    assert asked(made) == voice.ASK_TO


def test_without_a_list_on_the_page_the_station_is_typed_as_before() -> None:
    question = brief(stations=None).question()

    assert question is not None
    [field] = question.fields
    assert (field.type, field.options) == ("text", [])


def test_reading_the_list_touches_nothing_but_the_list() -> None:
    """`prepare` asks the page for its lists and does nothing else to it —
    `ListedPage` has no other method a click or a fill could reach."""
    page = ListedPage(STATIONS)
    made = TripBrief("g", Understood(), today=TODAY)

    run(made.prepare(page))

    assert made.stations == STATIONS and page.evaluated >= 2


@pytest.mark.parametrize("typed, station", [
    ("Lahore Jn", "LAHORE JN."),
    ("lahore  cantt", "LAHORE CANTT"),
    ("Rawalpindi", "RAWALPINDI"),
    # One station begins with it, or has it in its name: that one.
    ("Hyderabad", "HYDERABAD JN."),
    ("pindi", "RAWALPINDI"),
])
def test_a_name_that_is_one_station(typed: str, station: str) -> None:
    assert match_station(typed, STATIONS).station == station


def test_a_city_with_two_stations_is_both() -> None:
    assert match_station("Lahore", STATIONS).several == ("LAHORE JN.", "LAHORE CANTT")


def test_more_stations_than_can_be_offered_are_too_many() -> None:
    assert match_station("Kot", STATIONS).many


# --- a station that is not on the list -----------------------------------------


def test_a_misspelt_station_is_offered_the_closest_names() -> None:
    made = brief()
    made.question()

    made.answered("confirm", {"origin": "Karachy"})

    assert asked(made) == voice.not_a_station("Karachy")
    assert labels(made) == ["Karachi Cantt", "Karachi City", voice.NONE_OF_THESE, voice.STOP]
    made.answered(*choice(1))
    assert made.chosen["origin"] == "KARACHI CITY"


def test_none_of_the_closest_goes_back_to_the_whole_list() -> None:
    made = brief()
    made.question()
    made.answered("confirm", {"origin": "Karachy"})
    made.question()

    made.answered(*choice(2))  # None of these

    question = made.question()
    assert question is not None and question.instruction == voice.ASK_FROM
    assert question.fields[0].options == STATIONS


def test_a_name_nothing_on_the_list_is_close_to_says_so_and_asks_again() -> None:
    made = brief()
    made.question()

    made.answered("confirm", {"origin": "Zzyzx"})

    question = made.question()
    assert question is not None
    assert question.note == voice.not_a_station("Zzyzx")
    assert question.instruction == voice.ASK_FROM
    assert question.fields[0].options == STATIONS
    assert made.chosen["origin"] is None


def test_a_station_in_the_goal_that_is_not_on_the_list_is_asked_about_first() -> None:
    """Before anything is typed into the site — which is when the run used to
    find out, and end (`voice.no_station`)."""
    made = brief("trains from Karachy to Sukkur", origin="Karachy", destination="Sukkur",
                 day=TOMORROW)

    assert asked(made) == voice.not_a_station("Karachy")
    assert made.chosen["destination"] == "SUKKUR"


def test_a_city_with_two_stations_is_asked_about_before_anything_is_typed() -> None:
    made = brief(origin="Lahore", destination="Karachi", day=TOMORROW)

    assert asked(made) == voice.which_station("Lahore")
    assert labels(made) == ["Lahore Jn.", "Lahore Cantt", voice.NONE_OF_THESE, voice.STOP]


def test_a_city_is_named_the_way_the_site_names_it() -> None:
    made = brief()
    made.question()

    made.answered("confirm", {"origin": "Lahor"})

    assert asked(made) == voice.which_station("Lahore")


def test_too_many_stations_for_a_name_asks_for_more_of_it() -> None:
    made = brief()
    made.question()

    made.answered("confirm", {"origin": "Kot"})

    assert asked(made) == voice.many_stations("Kot")


# --- from and to the same ---------------------------------------------------------


def test_the_same_station_both_ways_asks_where_to_again() -> None:
    made = brief()
    made.question()
    made.answered("confirm", {"origin": "Lahore Cantt"})
    made.question()

    made.answered("confirm", {"destination": "LAHORE CANTT"})

    assert made.chosen["destination"] is None
    assert asked(made) == voice.same_station("Lahore Cantt")
    made.answered("confirm", {"destination": "Rawalpindi"})
    assert made.chosen["destination"] == "RAWALPINDI"


def test_the_same_place_both_ways_in_the_goal_asks_where_to() -> None:
    made = brief("trains from Rawalpindi to Rawalpindi", origin="Rawalpindi",
                 destination="Rawalpindi", day=TOMORROW)

    assert made.chosen["origin"] == "RAWALPINDI"
    assert asked(made) == voice.same_station("Rawalpindi")


def test_the_same_place_both_ways_is_noticed_without_a_list_too() -> None:
    made = brief(stations=None, origin="Karachi", destination="karachi", day=TOMORROW)

    assert asked(made) == voice.same_station("Karachi")


def test_two_stations_in_one_city_are_not_the_same_station() -> None:
    made = brief()
    made.question()
    made.answered("confirm", {"origin": "Lahore Jn."})
    made.question()

    made.answered("confirm", {"destination": "Lahore Cantt"})

    assert made.chosen == {"origin": "LAHORE JN.", "destination": "LAHORE CANTT"}


# --- the day ----------------------------------------------------------------------


def test_the_day_is_offered_as_today_tomorrow_or_another() -> None:
    made = brief(origin="Rawalpindi", destination="Sukkur")

    assert labels(made) == [voice.DAY_TODAY, voice.DAY_TOMORROW, "Pick another day", voice.STOP]


@pytest.mark.parametrize("typed", ["yesterday", "5 October 2026", "2026-09-01", "1/10/2026"])
def test_a_day_in_the_past_is_said_to_have_passed(typed: str) -> None:
    made = brief()
    to_the_day(made)

    made.answered("confirm", {"day": typed})

    assert made.day is None
    reading = read_day(typed, TODAY)
    assert asked(made) == voice.day_gone(reading.said)
    assert asked(made).endswith("has already passed.")


@pytest.mark.parametrize("typed", ["3 November 2027", "2028-01-03", "3/1/2028"])
def test_a_day_further_ahead_than_can_be_looked_up_says_how_far(typed: str) -> None:
    made = brief()
    to_the_day(made)

    made.answered("confirm", {"day": typed})

    assert made.day is None
    assert asked(made) == voice.day_too_far("7 October 2027")


def test_the_last_day_that_can_be_looked_up_is_taken() -> None:
    made = brief()
    to_the_day(made)

    made.answered("confirm", {"day": "7 October 2027"})

    assert made.day == date(2027, 10, 7)


@pytest.mark.parametrize("typed, said", [
    ("31 February", "31 February"),
    ("February 30th", "30 February"),
    ("2027-02-29", "29 February 2027"),
    ("31/4", "31 April"),
    ("31 November 2026", "31 November 2026"),
])
def test_a_day_that_does_not_exist_says_so(typed: str, said: str) -> None:
    made = brief()
    to_the_day(made)

    made.answered("confirm", {"day": typed})

    assert made.day is None
    assert asked(made) == voice.no_such_day(said)


def test_a_bare_number_no_month_has_is_not_a_day() -> None:
    made = brief()
    to_the_day(made)

    made.answered("confirm", {"day": "45"})

    assert asked(made) == voice.no_such_day("day 45")


def test_something_that_is_not_a_day_at_all_is_not_caught() -> None:
    made = brief()
    to_the_day(made)

    made.answered("confirm", {"day": "45/13"})

    assert asked(made) == voice.DAY_NOT_CAUGHT


@pytest.mark.parametrize("goal, why", [
    ("trains to Sukkur on 31 February", voice.no_such_day("31 February")),
    ("trains to Sukkur yesterday", voice.day_gone("5 October")),
    ("trains to Sukkur on 3 November 2027", voice.day_too_far("7 October 2027")),
])
def test_a_bad_day_in_the_goal_is_said_when_the_day_is_asked(goal: str, why: str) -> None:
    known = run(understand("railways", goal, today=TODAY))
    made = TripBrief(goal, replace_origin(known, "Rawalpindi"), today=TODAY)

    assert known.day is None
    assert made.question().note == why
    assert made.question().instruction == voice.ASK_DAY
    assert labels(made)[:3] == [voice.DAY_TODAY, voice.DAY_TOMORROW, voice.DAY_PICK]


def replace_origin(known: Understood, origin: str) -> Understood:
    from dataclasses import replace

    return replace(known, origin=origin)


def test_a_bad_day_in_the_goal_is_not_mended_by_the_model() -> None:
    """Asked about 31 February, a model is liable to answer 3 March. The
    words show there is no such day, and that stands."""

    class Mending:
        async def read_details(self, system_prompt: str, goal: str) -> DetailsChoice:
            return DetailsChoice(destination="Sukkur", date="2027-03-03")

    known = run(understand("railways", "trains to Sukkur on 31 February",
                           model=Mending(), today=TODAY))

    assert known.day is None
    assert known.day_problem is not None and known.day_problem.problem == details.NO_SUCH_DAY


def test_asking_for_the_day_three_times_is_the_limit() -> None:
    made = brief()
    to_the_day(made)

    for typed in ("31 February", "yesterday", "2030-01-01"):
        assert made.question() is not None
        made.answered("confirm", {"day": typed})

    assert made.question() is None
    assert made.gave_up == voice.NOT_UNDERSTOOD
    assert MAX_TRIES == 3


# --- read back once, before anything is done ------------------------------------


def test_the_journey_is_read_back_once_before_starting() -> None:
    """The task's own sentence: "Lahore to Karachi, tomorrow, 7 October. Is
    that right?" — with the stations the person chose."""
    made = brief(origin="Lahore", destination="Karachi", day=TOMORROW)
    made.question()
    made.answered(*choice(1))  # Lahore Cantt
    made.question()
    made.answered(*choice(0))  # Karachi Cantt

    assert asked(made) == "Lahore Cantt to Karachi Cantt, tomorrow, 7 October. Is that right?"
    assert labels(made) == [voice.READ_BACK_YES, voice.READ_BACK_NO, voice.STOP]
    made.answered(*choice(0))
    assert made.question() is None


@pytest.mark.parametrize("day, words", [
    (TODAY, "today, 6 October"),
    (date(2026, 10, 16), "Friday 16 October"),
    (date(2027, 1, 5), "Tuesday 5 January 2027"),
])
def test_the_day_is_read_back_the_way_a_person_checks_it(day: date, words: str) -> None:
    assert voice.when_words(day, TODAY) == words


def test_no_changes_what_was_said_and_reads_it_back_again() -> None:
    made = brief(origin="Rawalpindi", destination="Sukkur", day=TOMORROW)
    made.question()
    made.answered(*choice(1))  # No, change something

    assert asked(made) == voice.ASK_CHANGE
    assert labels(made) == [voice.CHANGE_FROM, voice.CHANGE_TO, voice.CHANGE_DAY, voice.STOP]
    made.answered(*choice(1))  # Where to
    assert asked(made) == voice.ASK_TO
    made.answered("confirm", {"destination": "Quetta"})

    assert asked(made) == "Rawalpindi to Quetta, tomorrow, 7 October. Is that right?"


def test_the_plan_searches_the_stations_that_were_chosen() -> None:
    made = brief(origin="Lahore", destination="Rawalpindi", day=TOMORROW)
    made.question()
    made.answered(*choice(1))
    made.question()
    made.answered(*choice(0))

    planner, task = made.settle()

    assert isinstance(planner, TripPlanner)
    assert planner.stations == {"origin": "LAHORE CANTT", "destination": "RAWALPINDI"}
    assert {v.label: v.equals for v in task.about.holds}["From"] == "LAHORE CANTT"


# --- on the page, through the real loop -------------------------------------------

PORT = 5213
REPLICA_URL = f"http://127.0.0.1:{PORT}"
REPLICA_STATIONS = ["LAHORE JN", "LAHORE CANTT", "KARACHI CANTT", "KARACHI CITY",
                    "RAWALPINDI", "MULTAN CANTT", "PESHAWAR CANTT", "PESHAWAR CITY",
                    "FAISALABAD", "HYDERABAD JN", "SUKKUR", "QUETTA"]


@pytest.fixture(scope="module")
def railways() -> Iterator[str]:
    proc = subprocess.Popen(
        [sys.executable, "app.py"], cwd=REPO_ROOT / "replicas" / "railways",
        env={**os.environ, "PORT": str(PORT)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(REPLICA_URL)
        yield REPLICA_URL
    finally:
        proc.terminate()
        proc.wait(timeout=10)


class Answering(ScriptedConnection):
    """Answers each question from the script in turn and agrees to every step.
    When the journey is read back, it looks at the page first: by then nothing
    on it may have been touched."""

    def __init__(self, answers, page=None) -> None:
        super().__init__(answers)
        self.page = page
        self.at_read_back: dict | None = None

    async def receive(self, message_type: str, step_index: int | None = None,
                      on_other=None) -> dict:  # noqa: ARG002
        self.shown += 1
        step = self.of("step.presented")[-1]
        ids = [action["id"] for action in step["actions"]]
        question = any(i.startswith(CHOICE_PREFIX) for i in ids) or any(
            action["label"] in TYPED_ANSWERS for action in step["actions"])
        if step["instruction"].endswith("Is that right?") and self.page is not None:
            self.at_read_back = await self.page.evaluate(
                "({model: {...window.__model}, searched: window.__searched,"
                " from: document.getElementById('from').value,"
                " to: document.getElementById('to').value,"
                " date: document.getElementById('date').value})")
        answer = ("confirm", {})
        if question:
            answer = (self.answers.pop(0) if self.answers else None) or (CANCEL_ID, {})
        return {"type": "step.response",
                "payload": {"step_index": step_index, "action_id": answer[0],
                            "input_values": answer[1]}}


def journey(goal: str, answers, start_url: str) -> Answering:
    """The goal read as the app reads it (keywords), then the real loop."""

    async def go() -> Answering:
        today = date.today()
        known = await understand("railways", goal, today=today)
        made = TripBrief(goal, known, today=today)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            connection = Answering(answers, page)
            try:
                await run_brief(page, connection, made, start_url)
                connection.searched = await page.evaluate("window.__searched")
            finally:
                await browser.close()
        return connection

    return run(go())


def test_a_goal_that_names_cities_asks_which_stations_then_reads_back(railways: str) -> None:
    """The task's own example, start to end on our copy of the site."""
    tomorrow = date.today() + timedelta(days=1)
    run = journey("train from Lahore to Karachi tomorrow",
                  [choice(1), choice(0), choice(0)], railways)

    instructions = run.instructions()
    assert instructions[:3] == [
        voice.which_station("Lahore"), voice.which_station("Karachi"),
        f"Lahore Cantt to Karachi Cantt, {voice.when_words(tomorrow, date.today())}. "
        "Is that right?",
    ]
    # Nothing had been done to the site while the questions were asked.
    assert run.at_read_back == {"model": {"from": "", "to": "", "date": ""},
                                "searched": None, "from": "", "to": "", "date": ""}
    assert run.searched == {"from": "LAHORE CANTT", "to": "KARACHI CANTT",
                            "date": tomorrow.isoformat()}
    # Read back once: the search step does not say the journey again.
    assert instructions[-1] == voice.READY_TO_SEARCH
    assert sum(i.endswith("Is that right?") for i in instructions) == 1
    assert "task.completed" in run.types()


def test_a_goal_that_names_nothing_asks_from_the_sites_list(railways: str) -> None:
    """Every bad answer on one run: the same station both ways, a day not in
    the calendar, a day gone. Each is said and asked again, and the search
    sent is the journey finally agreed."""
    tomorrow = date.today() + timedelta(days=1)
    run = journey("train", [
        ("confirm", {"origin": "Lahore Cantt"}),
        ("confirm", {"destination": "Lahore Cantt"}),
        ("confirm", {"destination": "Rawalpindi"}),
        choice(2),
        ("confirm", {"day": "31 February"}),
        ("confirm", {"day": "yesterday"}),
        ("confirm", {"day": "tomorrow"}),
        choice(0),
    ], railways)

    first = run.of("step.presented")[0]
    assert first["fields"][0]["options"] == REPLICA_STATIONS
    yesterday = date.today() - timedelta(days=1)
    led = [p.get("note") or p["instruction"] for p in run.of("step.presented")]
    assert led[:7] == [
        voice.ASK_FROM, voice.ASK_TO, voice.same_station("Lahore Cantt"), voice.ASK_DAY,
        voice.ASK_WHICH_DAY, voice.no_such_day("31 February"),
        voice.day_gone(voice.day_words(yesterday, date.today())),
    ]
    assert run.at_read_back["searched"] is None and run.at_read_back["from"] == ""
    assert run.searched == {"from": "LAHORE CANTT", "to": "RAWALPINDI",
                            "date": tomorrow.isoformat()}


def test_a_station_the_site_does_not_have_is_caught_before_the_site_is_touched(
    railways: str,
) -> None:
    """Until 2026-10-06 this typed "NARNIA" into the box, waited for a list,
    typed it again, and then ended the run (`test_trip.py`). Now the name is
    held to the list first, and the run carries on with another."""
    run = journey("trains from Narnia to Multan tomorrow", [
        ("confirm", {"origin": "Sukkur"}),
        None,  # stop at the reading back
    ], railways)

    first = run.of("step.presented")[0]
    assert (first["note"], first["instruction"]) == (voice.not_a_station("Narnia"),
                                                     voice.ASK_FROM)
    assert run.instructions()[1].startswith("Sukkur to Multan Cantt, tomorrow")
    assert run.searched is None
    assert run.at_read_back["from"] == "" and run.at_read_back["model"]["from"] == ""
    assert "task.failed" in run.types()


# --- the real app, launched as run.ps1 launches it, with no model quota ----------


class NoQuota(BaseHTTPRequestHandler):
    """An OpenAI-compatible endpoint whose account has no quota left."""

    calls = 0

    def do_POST(self) -> None:  # noqa: N802
        NoQuota.calls += 1
        body = json.dumps({"error": {"message": "You exceeded your current quota.",
                                     "type": "insufficient_quota",
                                     "code": "insufficient_quota"}}).encode()
        self.send_response(429)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: ARG002
        pass


APP_PORT = 8027


@pytest.fixture(scope="module")
def app_without_quota(railways: str) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), NoQuota)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {
        **os.environ,
        # The default router: one call to the configured model.
        "SIMBA_ROUTER": "model",
        "SIMBA_LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "no-quota-left",
        "OPENAI_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}/v1",
        "SIMBA_USE_HARDCODED_PLAN": "1",
        "SIMBA_RAILWAYS_URL": railways,
        "SIMBA_RECORD_STEPS": "0",
        "SIMBA_FLOW": "",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.orchestrator.app:app",
         "--port", str(APP_PORT)],
        cwd=REPO_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(f"http://127.0.0.1:{APP_PORT}")
        yield f"ws://127.0.0.1:{APP_PORT}/ws"
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        server.shutdown()


def converse(url: str, start: dict, answers: list) -> list[dict]:
    """One task over the websocket, answering questions from the script."""

    async def talk() -> list[dict]:
        received: list[dict] = []
        async with websockets.connect(url, max_size=None) as ws:
            seq = 0

            async def send(kind: str, payload: dict) -> None:
                nonlocal seq
                seq += 1
                await ws.send(json.dumps({"v": 1, "type": kind, "task_id": "t", "seq": seq,
                                          "ts": 0, "payload": payload}))

            await send("task.start", {"input_mode": "text", **start})
            while True:
                message = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
                received.append(message)
                kind, payload = message["type"], message["payload"]
                if kind == "step.presented":
                    ids = [a["id"] for a in payload["actions"]]
                    is_question = any(i.startswith(CHOICE_PREFIX) for i in ids) or any(
                        a["label"] in TYPED_ANSWERS for a in payload["actions"])
                    answer = answers.pop(0) if is_question and answers else ("confirm", {})
                    action, values = answer or (CANCEL_ID, {})
                    await send("step.response", {"step_index": payload["step_index"],
                                                 "action_id": action, "input_values": values})
                if kind in ("task.completed", "task.failed", "help.requested",
                            "goal.answered"):
                    return received

    return run(talk())


def test_the_default_launch_with_no_model_quota_asks_and_searches(
    app_without_quota: str,
) -> None:
    NoQuota.calls = 0
    received = converse(app_without_quota, {"goal": "find trains"}, [
        ("confirm", {"origin": "Hyderabad Jn"}),
        ("confirm", {"destination": "Sukkur"}),
        choice(1),
        choice(0),
    ])

    shown = [m["payload"]["instruction"] for m in received if m["type"] == "step.presented"]
    assert shown[:3] == [voice.ASK_FROM, voice.ASK_TO, voice.ASK_DAY]
    assert shown[3].startswith("Hyderabad Jn to Sukkur, tomorrow")
    assert received[-1]["type"] == "task.completed", [m["type"] for m in received]
    # The model was asked, and had nothing to give: routing and reading both fell
    # back to the keywords.
    assert NoQuota.calls >= 2


def test_the_train_card_asks_where_and_when(app_without_quota: str) -> None:
    """The cause of 2026-10-06: the card's own words named Lahore and Karachi.
    It now says what it does without naming a journey (`copy.ts`), so pressing
    it asks for all three."""
    received = converse(app_without_quota, {"goal": "Find train times", "flow": "railways"},
                        [None])

    first = next(m["payload"] for m in received if m["type"] == "step.presented")
    assert first["instruction"] == voice.ASK_FROM
    started = next(m["payload"] for m in received if m["type"] == "task.started")
    assert started["estimated_steps"] == 3 + 1 + TripBrief.plan_steps
    # Where the person is, by name, from the start (2026-10-14).
    assert started["stages"] == ["From", "To", "Day", "Search", "Trains"]
    assert first["stage"] == 0



def test_every_wrong_answer_is_a_note_beside_the_plain_question() -> None:
    """What was wrong is said in one sentence beside the question, never in
    it (2026-10-14), so the overlay can clear it once it is put right and the
    question still reads on its own."""
    made = brief()
    seen = []
    for answer in (("confirm", {"origin": "Narnia"}),              # nothing near it
                   ("confirm", {"origin": "Karachy"}),             # the nearest offered
                   choice(0),                                      # Karachi Cantt
                   ("confirm", {"destination": "Karachi Cantt"}),  # the same station
                   ("confirm", {"destination": "Sukkur"}),
                   choice(2),
                   ("confirm", {"day": "yesterday"})):
        question = made.question()
        seen.append((question.note, question.instruction))
        made.answered(*answer)
    question = made.question()
    seen.append((question.note, question.instruction))

    assert seen[0] == (None, voice.ASK_FROM)
    assert (voice.not_a_station("Narnia"), voice.ASK_FROM) in seen
    assert (voice.not_a_station("Karachy"), voice.ASK_CLOSEST) in seen
    assert (voice.same_station("Karachi Cantt"), voice.ASK_TO) in seen
    assert (voice.day_gone(voice.day_words(TODAY - timedelta(days=1), TODAY)),
            voice.ASK_TRAVEL_DAY) in seen
    # Which of a city's stations is not a wrong answer: no note.
    lahore = brief(origin="Lahore")
    assert (lahore.question().note, lahore.question().instruction) == (
        None, voice.which_station("Lahore"))
