"""Subprocess helpers — wrap kicad-cli and kibot with timeouts + structured output."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("kicad_mcp.runner")

DEFAULT_TIMEOUT = 300  # 5 min — generous for DRC on a large board


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    duration_s: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _which(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise RuntimeError(f"{binary!r} not found on PATH. Check the image build.")
    return path


async def _run(cmd: list[str], cwd: Path, timeout: int = DEFAULT_TIMEOUT) -> RunResult:
    log.info("run cwd=%s cmd=%s", cwd, cmd)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={
            **os.environ,
            # KiCad needs an X server even in CLI mode (kicad-cli sch erc etc).
            # The image bundles xvfb-run; kibot's KiAuto layer uses it
            # automatically. Make sure DISPLAY is set for our direct kicad-cli
            # calls too.
            "DISPLAY": os.environ.get("DISPLAY", ":99"),
            "HOME": os.environ.get("HOME", "/home/app"),
        },
    )
    import time

    start = time.monotonic()
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError(f"Command timed out after {timeout}s: {' '.join(cmd)}")
    duration = time.monotonic() - start
    result = RunResult(
        returncode=proc.returncode if proc.returncode is not None else -1,
        stdout=stdout_b.decode("utf-8", errors="replace"),
        stderr=stderr_b.decode("utf-8", errors="replace"),
        duration_s=round(duration, 2),
    )
    log.info("run done rc=%d duration=%.2fs", result.returncode, result.duration_s)
    return result


# ── kicad-cli wrappers ──────────────────────────────────────────────────────────


async def run_erc(project_dir: Path, schematic: Path) -> RunResult:
    """Run Electrical Rules Check on a .kicad_sch. Fails (rc != 0) on ERC errors."""
    cmd = [_which("kicad-cli"), "sch", "erc", "--exit-code-violations", str(schematic)]
    return await _run(cmd, cwd=project_dir)


async def run_drc(project_dir: Path, board: Path, *, units: str = "mm") -> RunResult:
    """Run Design Rules Check on a .kicad_pcb. Fails (rc != 0) on DRC errors."""
    cmd = [
        _which("kicad-cli"),
        "pcb",
        "drc",
        "--exit-code-violations",
        "--units",
        units,
        str(board),
    ]
    return await _run(cmd, cwd=project_dir)


async def export_gerbers(
    project_dir: Path,
    board: Path,
    output_dir: Path,
    *,
    layers: str = "all",
    use_gerber_x2: bool = True,
) -> RunResult:
    """Export Gerbers via kicad-cli. layers is a comma-separated list or 'all'."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [_which("kicad-cli"), "pcb", "export", "gerbers"]
    if use_gerber_x2:
        cmd.append("--use-gerber-x2-attributes")
    cmd += ["-o", str(output_dir) + "/", "-l", layers, str(board)]
    return await _run(cmd, cwd=project_dir)


async def export_drill(
    project_dir: Path,
    board: Path,
    output_dir: Path,
    *,
    format: str = "excellon",
    units: str = "mm",
) -> RunResult:
    """Export drill files (Excellon or Gerber) via kicad-cli."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        _which("kicad-cli"),
        "pcb",
        "export",
        "drill",
        "--output-dir",
        str(output_dir),
        "--format",
        format,
        "--units",
        units,
        str(board),
    ]
    return await _run(cmd, cwd=project_dir)


async def export_step(
    project_dir: Path,
    board: Path,
    output_file: Path,
) -> RunResult:
    """Export a STEP 3D model of the board via kicad-cli."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        _which("kicad-cli"),
        "pcb",
        "export",
        "step",
        "--output",
        str(output_file),
        str(board),
    ]
    return await _run(cmd, cwd=project_dir)


# ── kibot wrapper ───────────────────────────────────────────────────────────────


async def run_kibot(
    project_dir: Path,
    config_file: Path | None = None,
    *,
    targets: list[str] | None = None,
    output_dir: Path | None = None,
    skip_preflights: list[str] | None = None,
    timeout: int = 600,
) -> RunResult:
    """Run kibot. If config_file is None, kibot auto-discovers *.kibot.yaml."""
    cmd = [_which("kibot")]
    if config_file:
        cmd += ["-c", str(config_file)]
    if output_dir:
        cmd += ["-d", str(output_dir)]
    if targets:
        cmd += ["-t", ",".join(targets)]
    if skip_preflights:
        cmd += ["--skip", ",".join(skip_preflights)]
    return await _run(cmd, cwd=project_dir, timeout=timeout)


# ── sunshine creds ──────────────────────────────────────────────────────────────
# First-run Sunshine credentials helper. The MCP server does NOT do this in v1
# (the kicad-desktop pod handles it via an init step), but the helper is here
# for completeness so a future tool can rotate credentials via MCP.


async def sunshine_set_credentials(username: str, _password: str) -> RunResult:
    """Set Sunshine Web UI credentials via the `sunshine creds` subcommand.

    NOTE: This runs against the Sunshine binary inside the kicad-desktop pod,
    not this MCP pod. It is exposed here for future IPC-style tooling; for now
    it is unused.
    """
    # This must run in the kicad-desktop container, not this one. Documenting
    # the shape only.
    raise NotImplementedError(
        "Sunshine credential setup must run in the kicad-desktop pod "
        "(via kubectl exec or a sidecar init step), not the MCP pod."
    )
