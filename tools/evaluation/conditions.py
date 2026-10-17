"""What a measurement was taken under, recorded beside the measurement.

On 2026-09-06 the hardcoded benchmark was recorded at 5.93s mean. On
2026-09-17 the same script, against that same commit, ran at 3.0s. The code
was ruled out, the installed packages were ruled out, and the cause was never
established — because the result file held ten numbers and nothing about the
machine, the interpreter, or what else was running (EVALUATION.md,
2026-09-17e).

So every script in this directory prints these conditions when it starts and
writes them into its result file. A number without them is not reproducible,
and the benchmark the report is built on must not have the same gap.

What is recorded, and why each one:

  * `taken_at`     when, with the offset, so a run can be lined up against
                   other logs and against what else was happening.
  * `git`          commit, branch, and whether the tree was dirty. A dirty
                   tree means the commit does not describe what ran.
  * `python`       the exact interpreter, and whether it is the project venv.
                   The 2026-09-06 script had no import path set up, so it
                   cannot have run the way it does now, and which Python it
                   used is unknown.
  * `playwright`   the package version, and the browser build when the script
                   has one. A different Chromium is a different measurement.
  * `model`        provider and model string. `*-latest` aliases move under
                   you (EVALUATION.md, "Configuration under test").
  * `switches`     the `SIMBA_*` environment variables that change behaviour,
                   so an ablation arm is recorded rather than remembered.
  * `machine`      platform, CPU count, and CPU load at the start. Load is
                   the one hypothesis for 2026-09-06 that could not be ruled
                   out, and it costs a second to sample.

`load_percent` is best-effort: `None` means it could not be read, which is
recorded as such rather than as zero.
"""

import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VENV = REPO_ROOT / "backend" / "venv"

# Everything that changes what a run does. Recorded whether set or not, so
# "not set" is stated rather than left to inference.
SWITCHES = (
    "SIMBA_FLOW",
    "SIMBA_USE_HARDCODED_PLAN",
    "SIMBA_TRACE_MEMORY",
    "SIMBA_BROWSER",
    "SIMBA_OVERLAY_DETECTION",
    "SIMBA_INFERRED_ROLES",
    "SIMBA_SETBACK_PLACEMENT",
    "SIMBA_LLM_PROVIDER",
    "SIMBA_LLM_EFFORT",
    "SIMBA_REPLICA_URL",
    "SIMBA_ADAPT",
)


def _run(*command: str, timeout: float = 10.0) -> str | None:
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                              cwd=REPO_ROOT)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def git_state() -> dict[str, Any]:
    commit = _run("git", "rev-parse", "HEAD")
    status = _run("git", "status", "--porcelain")
    return {
        "commit": commit[:12] if commit else None,
        "branch": _run("git", "rev-parse", "--abbrev-ref", "HEAD"),
        # A dirty tree means the commit above does not describe what ran.
        "dirty": None if status is None else bool(status),
    }


def load_percent() -> int | None:
    """CPU load now, as a percentage, or None if it cannot be read."""
    if hasattr(os, "getloadavg") and os.cpu_count():
        try:
            return round(os.getloadavg()[0] / os.cpu_count() * 100)
        except OSError:
            pass
    if platform.system() == "Windows":
        average = _run(
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "(Get-CimInstance Win32_Processor | "
            "Measure-Object -Property LoadPercentage -Average).Average",
        )
        if average and average.strip().isdigit():
            return int(average.strip())
    return None


def power() -> dict[str, Any]:
    """Whether the machine is on battery, its processor's speed at this
    instant as a percentage of its rated speed, and its free memory in MB —
    each None if it cannot be read.

    Added 2026-10-17: the backend suite took 805s on a commit on 2026-10-16
    and 1435s on the same commit a day later, and nothing recorded what the
    machine was doing either time. That day it was on battery with 1.2 GB of
    7.9 GB free; under load its processor still ran above rated speed, so the
    battery alone did not explain it. Every wall clock depends on these."""
    found: dict[str, Any] = {"on_battery": None, "charge_percent": None,
                             "cpu_performance_percent": None, "free_memory_mb": None}
    if platform.system() != "Windows":
        return found
    said = _run(
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "$b = Get-CimInstance Win32_Battery | Select-Object -First 1; "
        "$c = (Get-Counter '\\Processor Information(_Total)\\% Processor Performance' "
        "-SampleInterval 1 -MaxSamples 1).CounterSamples[0].CookedValue; "
        "$m = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory; "
        "'{0}|{1}|{2}|{3}' -f $(if ($b) { $b.BatteryStatus } else { '' }), "
        "$(if ($b) { $b.EstimatedChargeRemaining } else { '' }), [int]$c, [int]($m / 1024)",
    )
    if not said or said.count("|") != 3:
        return found
    status, charge, performance, free = (part.strip() for part in said.strip().split("|"))
    # Win32_Battery.BatteryStatus: 1 is discharging; 2 and above are on mains
    # (charging, charged, or the like). No battery at all: on mains.
    found["on_battery"] = status == "1" if status else False
    found["charge_percent"] = int(charge) if charge.isdigit() else None
    found["cpu_performance_percent"] = int(performance) if performance.isdigit() else None
    found["free_memory_mb"] = int(free) if free.isdigit() else None
    return found


def power_line(machine_power: dict[str, Any]) -> str:
    """`on battery (40%), processor at 48% of rated speed, 1200 MB free`, or
    what could not be read."""
    battery = machine_power.get("on_battery")
    parts = ["unknown power source" if battery is None else
             "ON BATTERY" + (f" ({machine_power['charge_percent']}%)"
                             if machine_power.get("charge_percent") is not None else "")
             if battery else "on mains"]
    speed = machine_power.get("cpu_performance_percent")
    if speed is not None:
        parts.append(f"processor at {speed}% of rated speed")
    free = machine_power.get("free_memory_mb")
    if free is not None:
        parts.append(f"{free} MB memory free")
    return "power       " + ", ".join(parts)


#: Read from `.env` when not in the environment, because that is where the
#: provider and model are configured and the scripts load it themselves later.
#: Only these names are ever read out of `.env` — never a key, and no value
#: from it reaches a result file except the provider and the model string.
FROM_DOTENV = ("SIMBA_LLM_PROVIDER", "OPENAI_MODEL", "ANTHROPIC_MODEL")


def _dotenv() -> dict[str, str]:
    path = REPO_ROOT / ".env"
    if not path.exists():
        return {}
    found = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        name, _, value = line.partition("=")
        if name.strip() in FROM_DOTENV and value.strip():
            found[name.strip()] = value.strip()
    return found


def model() -> dict[str, str | None]:
    """The provider and model a run would use, and where that was read from."""
    dotenv = _dotenv()
    configured = os.environ.get("SIMBA_LLM_PROVIDER") or dotenv.get("SIMBA_LLM_PROVIDER")
    provider = (configured or "anthropic").strip().lower()
    key = "OPENAI_MODEL" if provider == "openai" else "ANTHROPIC_MODEL"
    name = os.environ.get(key) or dotenv.get(key)
    return {
        "provider": provider,
        "model": name,
        "model_from": "environment" if os.environ.get(key) else (".env" if name else None),
    }


def package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def conditions(**extra: Any) -> dict[str, Any]:
    """Everything worth knowing about this run but the result.

    `extra` is for anything only the caller knows — pass `chromium=` with
    `browser.version` where a script has a browser, and `runs=` or similar
    for how much it did.
    """
    return {
        "taken_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git": git_state(),
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "project_venv": Path(sys.executable).is_relative_to(VENV),
        },
        "playwright": package_version("playwright"),
        **model(),
        "switches": {name: os.environ.get(name) for name in SWITCHES},
        "machine": {
            "platform": platform.platform(),
            "cpus": os.cpu_count(),
            "load_percent": load_percent(),
            "power": power(),
        },
        **extra,
    }


def banner(recorded: dict[str, Any] | None = None) -> str:
    """The conditions as a few lines to print before a run."""
    recorded = recorded if recorded is not None else conditions()
    git = recorded["git"]
    python = recorded["python"]
    machine = recorded["machine"]
    load = machine["load_percent"]
    switches = {name: value for name, value in recorded["switches"].items() if value is not None}
    lines = [
        "=" * 72,
        f"taken at    {recorded['taken_at']}",
        f"git         {git['commit']} on {git['branch']}"
        + (" — DIRTY TREE, the commit does not describe this run" if git["dirty"] else ""),
        f"python      {python['version']} at {python['executable']}"
        + ("" if python["project_venv"] else "  <- not the project venv"),
        f"playwright  {recorded['playwright']}"
        + (f", chromium {recorded['chromium']}" if recorded.get("chromium") else ""),
        f"model       {recorded['provider']} {recorded['model']}"
        + (f" (from {recorded['model_from']})" if recorded.get("model_from") else ""),
        f"machine     {machine['platform']}, {machine['cpus']} cpus, load "
        + (f"{load}%" if load is not None else "unknown"),
        power_line(machine.get("power") or {}),
        f"switches    {switches or 'none set'}",
        "=" * 72,
    ]
    return "\n".join(lines)


def record(path: Path | str, results: Any, **extra: Any) -> dict[str, Any]:
    """Write results with their conditions. Returns what was written.

    The shape is `{"conditions": {...}, "results": ...}`. Result files written
    before 2026-09-17 are bare lists or objects; anything reading them has to
    handle both, which is itself a reason the conditions belong in the file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"conditions": conditions(**extra), "results": results}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(banner())
