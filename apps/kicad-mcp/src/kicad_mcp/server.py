"""MCP tool definitions — the surface an LLM agent can call.

Tools are intentionally coarse-grained and read-mostly. The destructive tools
(kibot pipelines, gerber export) act on a project directory only; they do not
modify .kicad_sch / .kicad_pcb in place. That is deliberate — the LLM cannot
silently rewrite your board file. Edits go through the IPC API once KiCad 11
ships headless IPC support.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .projects import PROJECTS_DIR, list_projects, resolve_project, iter_kibot_configs
from .runner import (
    DEFAULT_TIMEOUT,
    RunResult,
    export_drill,
    export_gerbers,
    export_step,
    run_drc,
    run_erc,
    run_kibot,
)

log = logging.getLogger("kicad_mcp")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

mcp = FastMCP("kicad-mcp")


def _result_dict(r: RunResult) -> dict:
    return {
        "ok": r.ok,
        "returncode": r.returncode,
        "duration_s": r.duration_s,
        "stdout": r.stdout[-8192:],  # truncate; LLM context is precious
        "stderr": r.stderr[-4096:],
    }


# ── Discovery ───────────────────────────────────────────────────────────────────


@mcp.tool()
def list_kicad_projects() -> str:
    """List all KiCad projects under the projects volume.

    Returns JSON. Each entry has: name, path (relative), has_schematic, has_board.
    Use this first to discover what's available before opening a project.
    """
    return json.dumps(list_projects(), indent=2)


@mcp.tool()
def open_project(project_path: str) -> str:
    """Resolve a KiCad project path and report its files.

    Args:
        project_path: Relative path under /projects (e.g. "blinky/rev1") or the
                      full path to a .kicad_pro file. MUST be inside the projects
                      volume — paths that escape are rejected.

    Returns JSON: name, project_file, schematic (or null), board (or null), directory.
    """
    return json.dumps(resolve_project(project_path), indent=2)


@mcp.tool()
def list_kibot_configs(project_path: str) -> str:
    """List *.kibot.yaml config files in a project directory.

    Use this to discover which kibot pipelines are defined before running one.
    """
    project = resolve_project(project_path)
    configs = [str(p.relative_to(Path(project["directory"]).parent)) for p in iter_kibot_configs(Path(project["directory"]))]
    return json.dumps({"project": project["name"], "configs": configs}, indent=2)


# ── Quality checks ─────────────────────────────────────────────────────────────


@mcp.tool(description="Run Electrical Rules Check (ERC) on a project's schematic.")
async def run_electrical_rules_check(project_path: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Args:
        project_path: Relative path under /projects to the project directory.
        timeout: Max seconds to run (default 300).

    Returns JSON with ok, returncode, stdout, stderr, duration_s. rc != 0
    indicates ERC violations — read stderr for the violation list.
    """
    project = resolve_project(project_path)
    if not project["schematic"]:
        return json.dumps({"ok": False, "error": "Project has no .kicad_sch file"})
    r = await run_erc(Path(project["directory"]), Path(project["schematic"]))
    return json.dumps(_result_dict(r), indent=2)


@mcp.tool(description="Run Design Rules Check (DRC) on a project's PCB.")
async def run_design_rules_check(project_path: str, units: str = "mm", timeout: int = DEFAULT_TIMEOUT) -> str:
    """Args:
        project_path: Relative path under /projects to the project directory.
        units: 'mm' or 'in' (default mm).
        timeout: Max seconds to run (default 300).

    Returns JSON. rc != 0 indicates DRC violations.
    """
    project = resolve_project(project_path)
    if not project["board"]:
        return json.dumps({"ok": False, "error": "Project has no .kicad_pcb file"})
    r = await run_drc(Path(project["directory"]), Path(project["board"]), units=units)
    return json.dumps(_result_dict(r), indent=2)


# ── Export (manufacturing outputs) ─────────────────────────────────────────────


@mcp.tool(description="Export Gerber files for a project's PCB.")
async def export_gerber_files(
    project_path: str,
    output_subdir: str = "fab",
    layers: str = "all",
    use_gerber_x2: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Args:
        project_path: Relative path under /projects.
        output_subdir: Subdir of the project to write gerbers to (default 'fab').
        layers: Comma-separated KiCad layer names or 'all' (default 'all').
        use_gerber_x2: Use Gerber X2 attributes (default True).
        timeout: Max seconds to run.

    Returns JSON with the export result.
    """
    project = resolve_project(project_path)
    if not project["board"]:
        return json.dumps({"ok": False, "error": "Project has no .kicad_pcb file"})
    out = Path(project["directory"]) / output_subdir
    r = await export_gerbers(
        Path(project["directory"]),
        Path(project["board"]),
        out,
        layers=layers,
        use_gerber_x2=use_gerber_x2,
    )
    return json.dumps({**_result_dict(r), "output_dir": str(out)}, indent=2)


@mcp.tool(description="Export drill files (Excellon or Gerber drill) for a project's PCB.")
async def export_drill_files(
    project_path: str,
    output_subdir: str = "fab",
    drill_format: str = "excellon",
    units: str = "mm",
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Args:
        project_path: Relative path under /projects.
        output_subdir: Subdir of the project to write drill files to.
        drill_format: 'excellon' (default) or 'gerber'.
        units: 'mm' (default) or 'in'.
        timeout: Max seconds to run.

    Returns JSON with the export result.
    """
    project = resolve_project(project_path)
    if not project["board"]:
        return json.dumps({"ok": False, "error": "Project has no .kicad_pcb file"})
    out = Path(project["directory"]) / output_subdir
    r = await export_drill(
        Path(project["directory"]),
        Path(project["board"]),
        out,
        format=drill_format,
        units=units,
    )
    return json.dumps({**_result_dict(r), "output_dir": str(out)}, indent=2)


@mcp.tool(description="Export a STEP 3D model of the assembled PCB.")
async def export_step_model(
    project_path: str,
    output_filename: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Args:
        project_path: Relative path under /projects.
        output_filename: Filename for the .step file (default: <project>.step).
        timeout: Max seconds to run.

    Returns JSON with the export result + absolute path to the STEP file.
    """
    project = resolve_project(project_path)
    if not project["board"]:
        return json.dumps({"ok": False, "error": "Project has no .kicad_pcb file"})
    out_dir = Path(project["directory"]) / "fab"
    out_file = out_dir / (output_filename or f"{project['name']}.step")
    r = await export_step(
        Path(project["directory"]),
        Path(project["board"]),
        out_file,
    )
    return json.dumps({**_result_dict(r), "output_file": str(out_file)}, indent=2)


# ── KiBot pipeline runner ───────────────────────────────────────────────────────


@mcp.tool(description="Run a kibot pipeline (config.kibot.yaml) against a project. Generates fab outputs.")
async def run_kibot_pipeline(
    project_path: str,
    config_filename: str | None = None,
    targets: list[str] | None = None,
    output_subdir: str = "fab",
    skip_preflights: list[str] | None = None,
    timeout: int = 600,
) -> str:
    """Args:
        project_path: Relative path under /projects.
        config_filename: Name of the *.kibot.yaml to use. If None, kibot auto-discovers.
        targets: Only run these named outputs (kibot -t). If None, runs all.
        output_subdir: Subdir of the project to write outputs to (default 'fab').
        skip_preflights: List of preflights to skip (e.g. ['drc', 'erc']).
        timeout: Max seconds to run (default 600).

    Returns JSON with the kibot result.
    """
    project = resolve_project(project_path)
    config = None
    if config_filename:
        config = Path(project["directory"]) / config_filename
        if not config.exists():
            return json.dumps({"ok": False, "error": f"kibot config not found: {config_filename}"})
    out_dir = Path(project["directory"]) / output_subdir
    r = await run_kibot(
        Path(project["directory"]),
        config_file=config,
        targets=targets,
        output_dir=out_dir,
        skip_preflights=skip_preflights,
        timeout=timeout,
    )
    return json.dumps({**_result_dict(r), "output_dir": str(out_dir)}, indent=2)


# ── Health (read by supergateway --healthEndpoint) ─────────────────────────────


def _health() -> dict:
    return {
        "ok": True,
        "version": "0.1.0",
        "projects_dir": str(PROJECTS_DIR),
        "projects_found": len(list_projects()),
    }


@mcp.tool(description="Health / sanity probe. Returns server version + projects volume status.")
def health() -> str:
    return json.dumps(_health(), indent=2)


def main() -> None:
    """Entrypoint — runs the MCP server on stdio (wrapped by supergateway)."""
    log.info("kicad-mcp starting; PROJECTS_DIR=%s", PROJECTS_DIR)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
