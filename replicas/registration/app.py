"""Local replica of a cluttered university course registration flow.

Three pages: login, course list (dense table + popup), confirmation.
Used for repeated benchmark runs against a stable target instead of a
live site (see CLAUDE.md).
"""

from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "replica-registration-not-for-prod"

COURSES = [
    {"crn": "10234", "subject": "CS", "number": "401", "section": "001", "title": "Advanced Widget Design", "credits": 3, "days": "MWF", "time": "10:00-10:50", "instructor": "Dr. Aslam", "room": "SCI 214", "seats": "28/40", "waitlist": 0, "attr": "STEM"},
    {"crn": "10235", "subject": "CS", "number": "220", "section": "002", "title": "Data Structures", "credits": 4, "days": "TTh", "time": "09:30-10:45", "instructor": "Dr. Rehman", "room": "SCI 118", "seats": "40/40", "waitlist": 6, "attr": "STEM"},
    {"crn": "10301", "subject": "MATH", "number": "210", "section": "001", "title": "Linear Algebra", "credits": 3, "days": "MWF", "time": "11:00-11:50", "instructor": "Dr. Iqbal", "room": "MTH 102", "seats": "35/50", "waitlist": 0, "attr": "STEM"},
    {"crn": "10302", "subject": "MATH", "number": "301", "section": "001", "title": "Probability Theory", "credits": 3, "days": "TTh", "time": "13:00-14:15", "instructor": "Dr. Farooq", "room": "MTH 210", "seats": "22/30", "waitlist": 0, "attr": "STEM"},
    {"crn": "10410", "subject": "ENGL", "number": "101", "section": "004", "title": "Composition I", "credits": 3, "days": "MWF", "time": "09:00-09:50", "instructor": "Prof. Siddiqui", "room": "HUM 305", "seats": "24/25", "waitlist": 0, "attr": "GENED"},
    {"crn": "10411", "subject": "ENGL", "number": "215", "section": "001", "title": "Technical Writing", "credits": 3, "days": "TTh", "time": "10:00-11:15", "instructor": "Prof. Bukhari", "room": "HUM 210", "seats": "18/25", "waitlist": 0, "attr": "GENED"},
    {"crn": "10512", "subject": "HIST", "number": "150", "section": "001", "title": "World Civilizations", "credits": 3, "days": "MWF", "time": "12:00-12:50", "instructor": "Dr. Zafar", "room": "HUM 101", "seats": "60/60", "waitlist": 12, "attr": "GENED"},
    {"crn": "10630", "subject": "BIOL", "number": "101", "section": "001", "title": "Introductory Biology", "credits": 4, "days": "MWF", "time": "08:00-08:50", "instructor": "Dr. Chaudhry", "room": "SCI 001", "seats": "55/60", "waitlist": 0, "attr": "STEM"},
    {"crn": "10631", "subject": "BIOL", "number": "101L", "section": "L02", "title": "Introductory Biology Lab", "credits": 1, "days": "W", "time": "14:00-16:50", "instructor": "Dr. Chaudhry", "room": "SCI 004", "seats": "20/24", "waitlist": 0, "attr": "STEM"},
    {"crn": "10702", "subject": "CHEM", "number": "111", "section": "001", "title": "General Chemistry I", "credits": 4, "days": "TTh", "time": "08:00-09:15", "instructor": "Dr. Malik", "room": "SCI 220", "seats": "48/50", "waitlist": 0, "attr": "STEM"},
    {"crn": "10803", "subject": "PHYS", "number": "201", "section": "001", "title": "Mechanics", "credits": 4, "days": "MWF", "time": "13:00-13:50", "instructor": "Dr. Hassan", "room": "SCI 310", "seats": "30/40", "waitlist": 0, "attr": "STEM"},
    {"crn": "10904", "subject": "ECON", "number": "101", "section": "001", "title": "Microeconomics", "credits": 3, "days": "TTh", "time": "11:30-12:45", "instructor": "Dr. Nawaz", "room": "BUS 105", "seats": "70/80", "waitlist": 0, "attr": "GENED"},
    {"crn": "11005", "subject": "PSYC", "number": "101", "section": "003", "title": "Introduction to Psychology", "credits": 3, "days": "MWF", "time": "10:00-10:50", "instructor": "Dr. Yousaf", "room": "HUM 220", "seats": "90/90", "waitlist": 20, "attr": "GENED"},
    {"crn": "11106", "subject": "ART", "number": "101", "section": "001", "title": "Introduction to Studio Art", "credits": 3, "days": "TTh", "time": "14:00-16:00", "instructor": "Prof. Anwar", "room": "ART 010", "seats": "15/18", "waitlist": 0, "attr": "GENED"},
    {"crn": "11207", "subject": "PHIL", "number": "205", "section": "001", "title": "Logic and Critical Thinking", "credits": 3, "days": "MWF", "time": "14:00-14:50", "instructor": "Dr. Qureshi", "room": "HUM 118", "seats": "26/30", "waitlist": 0, "attr": "GENED"},
    {"crn": "11308", "subject": "CS", "number": "350", "section": "001", "title": "Operating Systems", "credits": 3, "days": "TTh", "time": "15:30-16:45", "instructor": "Dr. Rehman", "room": "SCI 118", "seats": "33/35", "waitlist": 0, "attr": "STEM"},
    {"crn": "11309", "subject": "CS", "number": "460", "section": "001", "title": "Machine Learning", "credits": 3, "days": "MWF", "time": "15:00-15:50", "instructor": "Dr. Aslam", "room": "SCI 214", "seats": "40/40", "waitlist": 8, "attr": "STEM"},
    {"crn": "11410", "subject": "STAT", "number": "200", "section": "001", "title": "Applied Statistics", "credits": 3, "days": "TTh", "time": "09:30-10:45", "instructor": "Dr. Farooq", "room": "MTH 210", "seats": "38/45", "waitlist": 0, "attr": "STEM"},
    {"crn": "11511", "subject": "MUSC", "number": "110", "section": "001", "title": "Music Appreciation", "credits": 2, "days": "MW", "time": "13:00-13:50", "instructor": "Prof. Ali", "room": "ART 020", "seats": "40/45", "waitlist": 0, "attr": "GENED"},
    {"crn": "11612", "subject": "SOC", "number": "101", "section": "001", "title": "Introduction to Sociology", "credits": 3, "days": "TTh", "time": "12:30-13:45", "instructor": "Dr. Baig", "room": "HUM 220", "seats": "50/55", "waitlist": 0, "attr": "GENED"},
]


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["username"] = request.form.get("username") or "student"
        return redirect(url_for("courses"))
    return render_template("login.html")


@app.route("/courses")
def courses():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("courses.html", courses=COURSES, username=session["username"])


@app.route("/register", methods=["POST"])
def register():
    if "username" not in session:
        return redirect(url_for("login"))
    crn = request.form.get("crn")
    course = next((c for c in COURSES if c["crn"] == crn), None)
    if course is None:
        return redirect(url_for("courses"))
    confirmation_no = f"REG-{crn}-2026"
    return render_template(
        "confirm.html", course=course, username=session["username"], confirmation_no=confirmation_no
    )


if __name__ == "__main__":
    app.run(port=5000, debug=True)
