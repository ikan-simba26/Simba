# Billing replica

A local stand-in for a utility bill lookup flow, modelled on a Pakistani
electricity provider. No login. Repeated benchmark runs go against this,
never a live site (see CLAUDE.md).

It exists to stop perception pattern-matching a single page. Its clutter is
deliberately a different shape from `replicas/registration`:

| | registration | billing |
|---|---|---|
| Blocking chrome | full-screen modal backdrop | bottom cookie banner |
| Navigation | flat | breadcrumbs |
| Hidden content | none | accordions, collapsed by default |
| The value you want | in a labelled cell | in an unlabelled cell in a wide row |

## Pages

| Route | Page | What's on it |
|---|---|---|
| `/` | Bill enquiry | Reference-number form, two collapsed accordions, cookie banner |
| `/bill` | Enquiry result | Summary row with the payable amount, plus a 15-row tariff schedule that has nothing to do with it |
| `/bill/detail` | Bill detail | Line-by-line breakdown and a total |

Any non-empty reference number resolves. The worked example is
`04141234567890`.

## Run

```bash
cd replicas/billing
python -m venv venv
venv\Scripts\activate        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5100/. `PORT` overrides the port.
