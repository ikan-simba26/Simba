"""Local stand-in for the live train search.

The third flow runs against a real public site, and CLAUDE.md keeps repeated
runs off it. This is a page we wrote that behaves, in the ways that matter to
the loop, the way that site was measured to behave (EVALUATION.md, 2026-09-07
to 2026-09-09):

  * the station boxes are `readonly` until clicked;
  * typing a name opens a list of bare `<li>`s with no role, and the box only
    keeps a value that was chosen from it — typed text that was never chosen
    is thrown away when the box loses focus;
  * every station is in each list from the start, hidden until a name is
    typed, the way the live site's lists hold all their options at load
    (measured 2026-10-06) — so the list can be read without touching it;
  * typing a date puts it in the box and nowhere else: the application only
    believes a day picked from the calendar, whose cells are bare `<td>`s,
    and it writes the day back as `dd-mm-yyyy`;
  * the search button has no name;
  * searching changes no URL and no title, only a table.

It is not a copy of that site's markup or its timetable. The stations are a
short list that includes the cases the flow has to cope with — two stations
in one city, and a city with one — and the trains are invented. One route,
Hyderabad Jn to Sukkur, has four trains whose journey times repeat on rows
that are not next to each other (`search.html`, `SHARED`), for the results
travelling as whole rows (2026-10-05).

One page for the search. Everything there happens in the browser; `/`
serves it.

Since 2026-10-16 each train in the results can be booked: "Book" opens
`/book`, a form that needs a passenger's name and a class, and sending it
shows "Booking Confirmed" with a booking number, the train, the date and a
seat. Nothing is really booked and no money is taken, and the confirmation
says so. No live site is ever booked on (CLAUDE.md, the final-step rule).
"""

import os
import zlib

from flask import Flask, abort, render_template, request

app = Flask(__name__)

# Two in Lahore, two in Karachi, two in Peshawar: a place that names more
# than one station is the case the flow has to ask about.
STATIONS = [
    "LAHORE JN",
    "LAHORE CANTT",
    "KARACHI CANTT",
    "KARACHI CITY",
    "RAWALPINDI",
    "MULTAN CANTT",
    "PESHAWAR CANTT",
    "PESHAWAR CITY",
    "FAISALABAD",
    "HYDERABAD JN",
    "SUKKUR",
    "QUETTA",
]

# No trains run to or from here, so a search that comes back empty can be
# exercised without inventing a broken page.
NO_SERVICE = "QUETTA"


#: The classes a seat can be booked in, the booking form's own choices, and
#: what each costs on this invented railway.
CLASSES = [("Economy", "Rs 1,450"), ("AC Standard", "Rs 3,250"), ("AC Business", "Rs 5,100")]
#: Which coach each class is in.
COACHES = {"Economy": 6, "AC Standard": 3, "AC Business": 1}


@app.route("/")
def search():
    return render_template("search.html", stations=STATIONS, no_service=NO_SERVICE)


def _journey(source) -> dict[str, str]:
    """The journey a booking is for, as the results page passed it on."""
    journey = {key: (source.get(key) or "").strip()
               for key in ("train", "from", "to", "date", "leaves")}
    if not all(journey.values()):
        abort(400)
    return journey


@app.route("/book", methods=["GET"])
def book():
    journey = _journey(request.args)
    return render_template("book.html", train=journey["train"], origin=journey["from"],
                           destination=journey["to"], day=journey["date"],
                           leaves=journey["leaves"], classes=CLASSES, fares=dict(CLASSES))


@app.route("/book", methods=["POST"])
def booked():
    journey = _journey(request.form)
    passenger = (request.form.get("passenger") or "").strip()
    klass = request.form.get("class") or ""
    fares = dict(CLASSES)
    if not passenger or klass not in fares:
        abort(400)
    # Invented, and fixed for the same booking so a run reads the same twice.
    key = zlib.crc32(f"{journey['train']}|{journey['date']}|{passenger}|{klass}".encode())
    return render_template(
        "booked.html", booking=f"PR-{key % 1_000_000:06d}", passenger=passenger,
        train=journey["train"], origin=journey["from"], destination=journey["to"],
        day=journey["date"], leaves=journey["leaves"], klass=klass,
        seat=f"Coach {COACHES[klass]}, seat {key % 60 + 1}", fare=fares[klass])


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", "5200")))
