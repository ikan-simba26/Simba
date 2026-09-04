# Registration replica

A local stand-in for a cluttered university course registration flow. Repeated
benchmark runs go against this, never a live site (see CLAUDE.md).

Deliberately noisy: a 20-item main nav, a sidebar of announcements and quick
links, a footer link farm, dense legal boilerplate, a 14-column course table,
and a modal that covers the page on load and must be dismissed before anything
underneath can be clicked.

## Pages

| Route | Page | What's on it |
|---|---|---|
| `/` | Login | Username/password form, buried under notices and ~30 links |
| `/courses` | Course list | Modal on load, 14-column table of 20 sections, one Register button per row |
| `/register` (POST) | Confirmation | Confirmation number and course summary |

Any username and password are accepted — the login only needs to set a session.

## Run

```bash
cd replicas/registration
python -m venv venv
venv\Scripts\activate        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000/ — sign in with anything, dismiss the modal, and
register for a course.
