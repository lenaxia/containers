"""Project discovery + path safety helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

# Where projects live. Mounted from the shared Longhorn RWX PVC.
PROJECTS_DIR = Path(os.environ.get("PROJECTS_DIR", "/projects"))


def _safe_resolve(untrusted: str | Path) -> Path:
    """Resolve an untrusted path against PROJECTS_DIR and forbid escapes.

    Returns an absolute path inside PROJECTS_DIR. Raises ValueError if the
    resolved path is not inside PROJECTS_DIR (prevents path traversal from
    LLM-supplied arguments).
    """
    base = PROJECTS_DIR.resolve()
    candidate = (base / Path(untrusted)).resolve() if not Path(untrusted).is_absolute() else Path(untrusted).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(
            f"Path {untrusted!r} escapes PROJECTS_DIR ({base}). "
            "Only paths inside the projects volume are allowed."
        ) from exc
    return candidate


def list_projects() -> list[dict]:
    """Discover KiCad projects under PROJECTS_DIR (recursive).

    A "project" is any directory containing a *.kicad_pro file.
    """
    projects: list[dict] = []
    if not PROJECTS_DIR.exists():
        return projects
    for pro_path in sorted(PROJECTS_DIR.rglob("*.kicad_pro")):
        rel = pro_path.relative_to(PROJECTS_DIR).parent
        has_sch = (pro_path.parent / (pro_path.stem + ".kicad_sch")).exists()
        has_pcb = (pro_path.parent / (pro_path.stem + ".kicad_pcb")).exists()
        projects.append(
            {
                "name": pro_path.stem,
                "path": str(rel),
                "absolute_path": str(pro_path.parent),
                "has_schematic": has_sch,
                "has_board": has_pcb,
            }
        )
    return projects


def resolve_project(project_path: str) -> dict:
    """Resolve a project path to its files. Raises if not found."""
    base = _safe_resolve(project_path)
    if not base.exists():
        raise FileNotFoundError(f"Project path does not exist: {project_path}")
    # Allow pointing either at the project dir or directly at a .kicad_pro file.
    if base.is_file() and base.suffix == ".kicad_pro":
        pro = base
        base = base.parent
    else:
        pros = list(base.glob("*.kicad_pro"))
        if len(pros) != 1:
            raise FileNotFoundError(
                f"Expected exactly one .kicad_pro under {base}, found {len(pros)}"
            )
        pro = pros[0]
    sch = pro.parent / (pro.stem + ".kicad_sch")
    pcb = pro.parent / (pro.stem + ".kicad_pcb")
    return {
        "name": pro.stem,
        "project_file": str(pro),
        "schematic": str(sch) if sch.exists() else None,
        "board": str(pcb) if pcb.exists() else None,
        "directory": str(pro.parent),
    }


def iter_kibot_configs(project_dir: Path) -> Iterator[Path]:
    """Yield *.kibot.yaml files in a project directory (kibot's auto-discovery glob)."""
    yield from sorted(project_dir.glob("*.kibot.yaml"))
