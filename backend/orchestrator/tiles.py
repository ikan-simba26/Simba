"""The person's own tiles on the home screen (2026-10-18): "My bill", "Trains to
Karachi" — a task they did once, kept with the details they gave, to run again
with one press.

**Kept like the sign-in vault** (`vault.py`): encrypted with the operating
system's own key for this Windows account (DPAPI), in `data/tiles.json` beside
`vault.json`, never committed. The whole list is one encrypted blob — the
names too — so nothing about a tile is readable in the file. On a machine
where the vault cannot encrypt, there are no tiles and none is offered.

**Never sent to a model.** A tile's details become what the brief already
knows (`details.Understood`) directly: the goal is not read by the router or
by `understand`, so nothing a person kept reaches a prompt. The overlay is
sent each tile's id, name and flow only (`history.offered.tiles`); the details
stay here, and a tile is run by its id (`task.start.tile`).

Nothing here prints a detail: `Tile` has no readable `repr` for them.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass, field, replace
from pathlib import Path

from backend.orchestrator.vault import REPO, Vault, VaultUnavailable, decrypt, encrypt

DEFAULT_PATH = REPO / "data" / "tiles.json"
#: How many tiles a person can keep. One row on the home screen, at every
#: scaling; a fourth would push the box to ask in off the bottom at 150%.
MAX_TILES = 3
#: The longest name a tile keeps: one line on its card.
LABEL_MAX = 28
#: The flows a tile can be for, and the details each keeps.
KEEPS = {"billing": ("reference",), "railways": ("origin", "destination")}


@dataclass(frozen=True)
class Tile:
    id: str
    label: str
    flow: str
    details: dict[str, str] = field(default_factory=dict)

    def __repr__(self) -> str:  # never the details, whatever prints this
        return f"Tile(id={self.id!r}, flow={self.flow!r}, ...)"

    __str__ = __repr__


def clean_label(label: str) -> str:
    """A name as typed, tidied: spaces collapsed, cut to `LABEL_MAX`."""
    return " ".join((label or "").split())[:LABEL_MAX].strip()


class TileStore:
    """The tiles, in the person's order. Every change is written at once."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or os.environ.get("SIMBA_TILES") or DEFAULT_PATH)
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        """Whether this machine can encrypt a tile at all. Asked once."""
        if self._available is None:
            self._available = Vault().available
        return self._available

    def all(self) -> list[Tile]:
        if not self.available or not self.path.exists():
            return []
        try:
            blob = json.loads(self.path.read_text(encoding="utf-8"))["tiles"]
            rows = json.loads(decrypt(bytes.fromhex(blob)).decode("utf-8"))
        except (OSError, ValueError, KeyError, VaultUnavailable):
            # Unreadable — another account's, or damaged — is no tiles, not a
            # dead home screen.
            return []
        return [Tile(row["id"], row["label"], row["flow"], dict(row.get("details") or {}))
                for row in rows if row.get("flow") in KEEPS]

    def get(self, tile_id: str | None) -> Tile | None:
        return next((tile for tile in self.all() if tile.id == tile_id), None)

    def holds(self, flow: str, details: dict[str, str]) -> bool:
        """Whether a tile already keeps exactly this: then none is offered."""
        return any(tile.flow == flow and tile.details == details for tile in self.all())

    def can_keep(self, flow: str, details: dict[str, str]) -> bool:
        return (self.available and flow in KEEPS and len(self.all()) < MAX_TILES
                and not self.holds(flow, details))

    def add(self, label: str, flow: str, details: dict[str, str]) -> Tile | None:
        """Kept, at the end of the row; None if it cannot be."""
        details = {key: str(details[key]) for key in KEEPS.get(flow, ()) if details.get(key)}
        name = clean_label(label)
        if not name or not self.can_keep(flow, details) or set(details) != set(KEEPS[flow]):
            return None
        tile = Tile(secrets.token_hex(6), name, flow, details)
        self._write([*self.all(), tile])
        return tile

    def rename(self, tile_id: str, label: str) -> bool:
        name = clean_label(label)
        tiles = self.all()
        if not name or not any(tile.id == tile_id for tile in tiles):
            return False
        self._write([replace(tile, label=name) if tile.id == tile_id else tile
                     for tile in tiles])
        return True

    def move(self, tile_id: str, to: int) -> bool:
        tiles = self.all()
        moving = next((tile for tile in tiles if tile.id == tile_id), None)
        if moving is None:
            return False
        rest = [tile for tile in tiles if tile.id != tile_id]
        rest.insert(max(0, min(int(to), len(rest))), moving)
        self._write(rest)
        return True

    def remove(self, tile_id: str) -> bool:
        tiles = self.all()
        kept = [tile for tile in tiles if tile.id != tile_id]
        if len(kept) == len(tiles):
            return False
        self._write(kept)
        return True

    def clear(self) -> None:
        """Every tile gone, and the file with them: for the next person."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _write(self, tiles: list[Tile]) -> None:
        rows = [{"id": t.id, "label": t.label, "flow": t.flow, "details": t.details}
                for t in tiles]
        blob = encrypt(json.dumps(rows).encode("utf-8")).hex()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"tiles": blob}), encoding="utf-8")
