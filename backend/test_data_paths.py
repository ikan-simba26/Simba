"""The installed app's writable paths (2026-11-13).

Installed, the backend runs from a folder that is the program, and every file
it writes is moved into the person's profile folder by an environment
variable the host sets (`frontend/electron/backend.ts`, `dataEnvironment`).
These check that each variable the host sets is one the backend honours.

Each is read in a fresh interpreter: two of them are read at import time.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

PROBE = """
import json
from backend.estimator import pairing
from backend.orchestrator import llm, tiles, vault, routines, app, ai_settings, catalogue
print(json.dumps({
    "SIMBA_STEPS": str(pairing.DEFAULT_PATH),
    "SIMBA_LLM_LOG_DIR": str(llm.LOG_DIR),
    "SIMBA_TILES": str(tiles.TileStore().path),
    "SIMBA_VAULT": str(vault.Vault().path),
    "SIMBA_ROUTINES": str(routines.RoutineStore().path),
    "SIMBA_AI_SETTINGS": str(ai_settings.AiStore().path),
    "SIMBA_CATALOGUE_LOCAL": str(catalogue.CatalogueStore().local),
}))
"""


def _probe(env: dict[str, str]) -> dict[str, str]:
    result = subprocess.run(
        [sys.executable, "-c", PROBE], cwd=REPO, capture_output=True, text=True,
        env={**os.environ, "SIMBA_LOG_FILE": "", **env}, timeout=120, check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_every_path_the_host_moves_is_moved(tmp_path: Path) -> None:
    wanted = {
        "SIMBA_STEPS": str(tmp_path / "data" / "steps.jsonl"),
        "SIMBA_LLM_LOG_DIR": str(tmp_path / "logs"),
        "SIMBA_TILES": str(tmp_path / "data" / "tiles.json"),
        "SIMBA_VAULT": str(tmp_path / "data" / "vault.json"),
        "SIMBA_ROUTINES": str(tmp_path / "data" / "routines.json"),
        "SIMBA_AI_SETTINGS": str(tmp_path / "data" / "ai.json"),
        "SIMBA_CATALOGUE_LOCAL": str(tmp_path / "data" / "catalogue.local.json"),
    }
    assert _probe(wanted) == wanted


def test_unset_they_stay_in_the_repository() -> None:
    env = {name: "" for name in ("SIMBA_STEPS", "SIMBA_LLM_LOG_DIR")}
    seen = _probe(env)
    assert seen["SIMBA_STEPS"] == str(REPO / "data" / "steps.jsonl")
    assert seen["SIMBA_LLM_LOG_DIR"] == str(REPO / "logs")


def test_the_host_sets_exactly_these() -> None:
    host = (REPO / "frontend" / "electron" / "backend.ts").read_text(encoding="utf-8")
    for name in ("SIMBA_TILES", "SIMBA_VAULT", "SIMBA_ROUTINES", "SIMBA_TRACE_DB",
                 "SIMBA_STEPS", "SIMBA_LOG_FILE", "SIMBA_LLM_LOG_DIR", "SIMBA_ENV_FILE",
                 "SIMBA_HOST_PID", "SIMBA_AI_SETTINGS", "SIMBA_CATALOGUE_LOCAL"):
        assert f"{name}:" in host, name


def test_a_key_is_read_from_the_file_the_host_names(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SIMBA_TEST_ONLY_KEY=from-the-profile\n", encoding="utf-8")
    probe = ("import os\n"
             "from backend.orchestrator import llm\n"
             "llm._load_dotenv()\n"
             "print(os.environ.get('SIMBA_TEST_ONLY_KEY'))")
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO, capture_output=True, text=True,
        env={**os.environ, "SIMBA_LOG_FILE": "", "SIMBA_ENV_FILE": str(env_file)},
        timeout=120, check=True,
    )
    assert result.stdout.strip().splitlines()[-1] == "from-the-profile"
