from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "creature.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(_SCHEMA)


class ProjectValidationError(ValueError):
    pass


def validate_project(project: dict[str, Any], project_path: Path | None = None) -> None:
    errors = sorted(_VALIDATOR.iter_errors(project), key=lambda item: list(item.absolute_path))
    if errors:
        details = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "$"
            details.append(f"{location}: {error.message}")
        raise ProjectValidationError("\n".join(details))

    mod_id = project["project"]["modId"]
    creature_id = project["creature"]["id"]
    if mod_id in {"minecraft", "fabric", "fabricloader", "fabric_api", "java"}:
        raise ProjectValidationError(f"Reserved mod id: {mod_id}")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", mod_id):
        raise ProjectValidationError("modId is not a valid portable Fabric identifier")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,47}", creature_id):
        raise ProjectValidationError("creature.id is not a valid portable registry path")

    if project_path is not None:
        model_file = project["creature"]["model"]["file"]
        relative = Path(model_file)
        if relative.is_absolute() or ".." in relative.parts:
            raise ProjectValidationError("model.file must be a safe path relative to the project JSON")
        if not (project_path.parent / relative).is_file():
            raise ProjectValidationError(f"Model file does not exist: {model_file}")
