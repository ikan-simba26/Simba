"""Trace memory: what a successful run did, so it can be done again.

A trace records the *targets* of each action — the accessible role and label
— and never the integer element ids. Ids are assigned per perception pass and
shift whenever the page's element count changes, so a trace keyed on them
would be worthless on the next load. Role and label survive.

Storage is SQLite: one row per (goal, site), holding the ordered steps as
JSON. Re-recording the same pair replaces it, so a corrected trace supersedes
the one that no longer fits.
"""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = REPO_ROOT / "traces.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    goal        TEXT NOT NULL,
    site        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    steps       TEXT NOT NULL,
    PRIMARY KEY (goal, site)
)
"""


@dataclass(frozen=True)
class TraceStep:
    kind: str  # fill | click | select
    role: str
    label: str
    value: str | None = None


@dataclass(frozen=True)
class Trace:
    goal: str
    site: str
    created_at: str
    steps: list[TraceStep]

    def __len__(self) -> int:
        return len(self.steps)


def site_of(url: str) -> str:
    """The origin a trace belongs to. A different port is a different site."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


class TraceStore:
    def __init__(self, path: Path | str = DEFAULT_DB) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save(self, goal: str, site: str, steps: list[TraceStep]) -> None:
        """Remember this run, replacing any earlier trace for the same goal."""
        if not steps:
            return
        payload = json.dumps([asdict(step) for step in steps])
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO traces (goal, site, created_at, steps) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(goal, site) DO UPDATE SET steps=excluded.steps, "
                "created_at=excluded.created_at",
                (goal, site, datetime.now(timezone.utc).isoformat(), payload),
            )

    def find(self, goal: str, site: str) -> Trace | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT created_at, steps FROM traces WHERE goal = ? AND site = ?",
                (goal, site),
            ).fetchone()
        if row is None:
            return None
        created_at, payload = row
        return Trace(
            goal=goal,
            site=site,
            created_at=created_at,
            steps=[TraceStep(**step) for step in json.loads(payload)],
        )

    def forget(self, goal: str, site: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM traces WHERE goal = ? AND site = ?", (goal, site)
            )

    def recent(self, limit: int = 3) -> list[tuple[str, str]]:
        """The most recently recorded goals, newest first.

        `created_at` is an ISO-8601 UTC string, which sorts correctly as text,
        so the ordering does not need parsing.
        """
        with self._connect() as connection:
            return [
                (goal, site)
                for goal, site in connection.execute(
                    "SELECT goal, site FROM traces ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            ]

    def goals(self) -> list[tuple[str, str]]:
        with self._connect() as connection:
            return [
                (goal, site)
                for goal, site in connection.execute("SELECT goal, site FROM traces")
            ]
