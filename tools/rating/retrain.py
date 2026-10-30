"""More ratings in, a new estimator out: one command.

    python -m tools.rating.retrain "SIMBA rating form, Set 1.csv" "SIMBA rating form, Set 2.csv"

Reads the forms' CSVs as they are now (`from_form`, which replaces the online
rows of the sets it is given and keeps the in-person ones), trains on every
rating (`backend.estimator.train`), and holds the new model against the rules
(`tools.evaluation.estimator_compare`). Afterwards `data/estimator.joblib`,
`data/estimator.json` and `data/estimator_pages.json` are the new model's,
EVALUATION.md has two new sections, and the next connection to the backend
uses it. With no CSVs it trains on what `data/ratings.jsonl` already holds.

Under eight ratings on any page it refuses, as `train` does, and says how many
more of which set it takes. `--min-ratings 5` trains anyway, and says so
everywhere the result goes: only a person should make that choice.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.estimator import train
from tools.evaluation import estimator_compare
from tools.rating import from_form


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("csv", nargs="*", help="a form's responses, downloaded as CSV")
    parser.add_argument("--min-ratings", type=int, default=train.MIN_RATINGS,
                        help=f"train with fewer than {train.MIN_RATINGS} ratings on a page")
    args = parser.parse_args()
    if args.csv:
        try:
            print(from_form.summary(from_form.run([from_form.named(a) for a in args.csv])))
        except from_form.ConversionRefused as reason:
            print(f"Not converted: {reason}")
            raise SystemExit(2) from None
    try:
        trained = train.run(min_ratings=args.min_ratings)
    except train.RefusedToTrain as reason:
        print(f"Not training: {reason}")
        raise SystemExit(2) from None
    print(train.report(trained))
    print(estimator_compare.run([from_form.named(a)[1] for a in args.csv]))
    print(f"Saved {train.MODEL} and {train.COEFFICIENTS}; appended to {train.EVALUATION}.")


if __name__ == "__main__":
    main()
