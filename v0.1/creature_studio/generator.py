from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .blockbench import import_bbmodel
from .compiler import GenerationError, compile_project
from .schema import validate_project


def _write(root: Path, relative: str, data: str | bytes) -> None:
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise GenerationError(f"Generated path escapes project root: {relative}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        target.write_bytes(data)
    else:
        target.write_text(data, encoding="utf-8", newline="\n")


def generate(project_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    """Persist the deterministic in-memory compilation result to an output directory."""
    project_file = Path(project_path).resolve()
    try:
        project = json.loads(project_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenerationError(f"Cannot read creature project: {exc}") from exc
    validate_project(project, project_file)

    model_file = (project_file.parent / project["creature"]["model"]["file"]).resolve()
    if not model_file.is_relative_to(project_file.parent.resolve()):
        raise GenerationError("Model file escapes the creature project directory")
    model = import_bbmodel(model_file)
    model_source = model_file.read_bytes()

    compilation = compile_project(project, model, model_source)

    output = Path(output_path).resolve()
    if output.exists() and any(output.iterdir()):
        raise GenerationError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for relative, content in compilation.files.items():
        _write(output, relative, content)

    return {
        **compilation.report,
        "status": "GENERATED",
        "output": str(output),
        "gradleBuild": "NOT_RUN",
        "gameRuntime": "NOT_RUN",
    }
