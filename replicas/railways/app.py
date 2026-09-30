"""Local stand-in for the live train search.

The third flow runs against a real public site, and CLAUDE.md keeps repeated
runs off it. This is a page we wrote that behaves, in the ways that matter to
the loop, the way that site was measured to behave (EVALUATION.md, 2026-09-07
to 2026-09-09):

  * the station boxes are `readonly` until clicked;
  * typing a name opens a list of bare `<li>`s with no role, and the box only
    keeps a value that was chosen from it — typed text that was never chosen
    is thrown away when the box loses focus;
  * typing a date puts it in the box and nowhere else: the application only
    believes a day picked from the calendar, whose cells are bare `<td>`s,
    and it writes the day back as `dd-mm-yyyy`;
  * the search button has no name;
  * searching changes no URL and no title, only a table.

It is not a copy of that site's markup or its timetable. The stations are a
short list that includes the cases the flow has to cope with — two stations
in one city, and a city with one — and the trains are invented.

One page. Everything happens in the browser; `/` serves it.
"""

import os

from flask import Flask, render_template

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


@app.route("/")
def search():
    return render_template("search.html", stations=STATIONS, no_service=NO_SERVICE)


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", "5200")))
