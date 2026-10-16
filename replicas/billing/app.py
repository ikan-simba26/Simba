"""Local replica of a utility bill lookup flow.

Modelled on a Pakistani electricity provider. Three pages: enter a reference
number, read the amount due off a results page, open the detail breakdown.
No login. Since 2026-10-16 the bill can also be paid from its results page,
as a pretend payment with no card details: a page that states the amount,
and a receipt that says no money was taken.

Deliberately cluttered in a *different* shape from replicas/registration, so
perception has to generalise rather than pattern-match one page:

  registration            billing
  ----------------        -------------------------
  full-screen modal       bottom cookie banner
  flat page               breadcrumbs
  everything visible      accordion hiding content
  labelled table cells    the payable amount in an unlabelled cell
"""

import datetime
import os
import zlib

from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

# Any 14-digit reference resolves; this one is the worked example.
KNOWN_REFERENCE = "04141234567890"

BILL = {
    "reference": KNOWN_REFERENCE,
    "name": "M. R. WASIM",
    "address": "HOUSE 24, STREET 7, GULBERG III, LAHORE",
    "connection_date": "12-03-2019",
    "tariff": "A-1a(01) RESIDENTIAL",
    "load": "3.00 kW",
    "meter": "K80-4471192",
    "month": "AUG 2026",
    "units": 412,
    "reading_previous": 38714,
    "reading_current": 39126,
    "due_date": "15-09-2026",
    "payable_within": "14,382",
    "payable_after": "14,957",
    "issue_date": "01-09-2026",
    "status": "UNPAID",
}

BREAKDOWN = [
    ("Cost of electricity", "9,884.00"),
    ("Fuel price adjustment", "1,102.40"),
    ("Quarterly tariff adjustment", "612.00"),
    ("Electricity duty 1.5%", "148.26"),
    ("General sales tax 18%", "1,779.12"),
    ("TV licence fee", "35.00"),
    ("PTV surcharge", "0.00"),
    ("Meter rent", "25.00"),
    ("Financing cost surcharge", "296.22"),
    ("Arrears / adjustment", "500.00"),
]

# Unrelated tariff information that sits around the number the user wants.
TARIFF_SLABS = [
    ("A-1a(01)", "Residential", "Up to 100 units", "7.74", "Protected", "—"),
    ("A-1a(02)", "Residential", "101 - 200 units", "10.06", "Protected", "—"),
    ("A-1a(03)", "Residential", "001 - 100 units", "13.48", "Unprotected", "—"),
    ("A-1a(04)", "Residential", "101 - 200 units", "18.95", "Unprotected", "—"),
    ("A-1a(05)", "Residential", "201 - 300 units", "22.14", "Unprotected", "—"),
    ("A-1a(06)", "Residential", "301 - 400 units", "25.53", "Unprotected", "1.00"),
    ("A-1a(07)", "Residential", "401 - 500 units", "27.74", "Unprotected", "1.00"),
    ("A-1a(08)", "Residential", "501 - 600 units", "29.16", "Unprotected", "1.50"),
    ("A-1a(09)", "Residential", "601 - 700 units", "30.30", "Unprotected", "1.50"),
    ("A-1a(10)", "Residential", "Above 700 units", "35.24", "Unprotected", "2.00"),
    ("A-2(a)", "Commercial", "Up to 5 kW", "40.71", "—", "2.00"),
    ("A-2(b)", "Commercial", "Above 5 kW", "43.36", "—", "2.00"),
    ("B-1", "Industrial", "Up to 25 kW", "38.94", "—", "1.00"),
    ("B-2(a)", "Industrial", "26 - 500 kW", "37.55", "—", "1.00"),
    ("C-1(a)", "Bulk supply", "Up to 5 kW", "41.02", "—", "2.00"),
]


@app.route("/")
def lookup():
    return render_template("lookup.html", error=request.args.get("error"))


@app.route("/bill", methods=["GET", "POST"])
def bill():
    reference = (request.form.get("reference") or request.args.get("reference") or "").strip()
    if not reference:
        return redirect(url_for("lookup", error="Enter a reference number to continue."))
    return render_template("results.html", bill=BILL, slabs=TARIFF_SLABS, reference=reference)


@app.route("/bill/detail")
def detail():
    reference = (request.args.get("reference") or KNOWN_REFERENCE).strip()
    total = "14,382.00"
    return render_template(
        "detail.html", bill=BILL, breakdown=BREAKDOWN, total=total, reference=reference
    )


@app.route("/bill/pay", methods=["GET", "POST"])
def pay():
    """A pretend payment (2026-10-16): the bill's amount, no card and no
    choice, and a receipt once confirmed. No money is taken, and the receipt
    says so."""
    reference = (request.values.get("reference") or "").strip()
    if not reference:
        return redirect(url_for("lookup", error="Enter a reference number to continue."))
    if request.method == "GET":
        return render_template("pay.html", bill=BILL, reference=reference)
    receipt = f"RCPT-{zlib.crc32(reference.encode()) % 1_000_000:06d}"
    paid_on = datetime.date.today().strftime("%d-%m-%Y")
    return render_template("receipt.html", bill=BILL, reference=reference, receipt=receipt,
                           paid_on=paid_on)


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", "5100")))
