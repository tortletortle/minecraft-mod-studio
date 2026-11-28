from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .behavior_graph import validate_graph
from .state_machine import validate as validate_state_machine

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "creature.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(_SCHEMA)


class ProjectValidationError(ValueError):
    pass


_VERSION_PATTERN = re.compile(r"^[0-9A-Za-z.+_-]{1,64}$")
_JAVA_RESERVED_IDENTIFIERS = frozenset({
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else", "enum",
    "extends", "final", "finally", "float", "for", "goto", "if", "implements",
    "import", "instanceof", "int", "interface", "long", "native", "new",
    "package", "private", "protected", "public", "return", "short", "static",
    "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "void", "volatile", "while", "true", "false", "null",
    "_", "exports", "module", "open", "opens", "permits", "provides", "record",
    "requires", "sealed", "transitive", "to", "uses", "var", "when", "with",
    "yield", "non-sealed",
})


def validate_project(project: dict[str, Any], project_path: Path | None = None) -> None:
    errors = sorted(_VALIDATOR.iter_errors(project), key=lambda item: list(item.absolute_path))
    if errors:
        details = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "$"
            details.append(f"{location}: {error.message}")
        raise ProjectValidationError("\n".join(details))

    creature = project["creature"]
    if "behavior_graph" in project:
        try:
            graph_errors = validate_graph(project["behavior_graph"])
        except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
            raise ProjectValidationError(
                f"behavior_graph validation failed: malformed configuration ({exc})"
            ) from exc
        if graph_errors:
            details = "\n".join(f"- {error}" for error in graph_errors)
            raise ProjectValidationError(f"behavior_graph validation failed:\n{details}")

    if "state_machine" in project:
        try:
            state_errors = validate_state_machine(project["state_machine"], creature)
        except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
            raise ProjectValidationError(
                f"state_machine validation failed: malformed configuration ({exc})"
            ) from exc
        if state_errors:
            details = "\n".join(f"- {error}" for error in state_errors)
            raise ProjectValidationError(f"state_machine validation failed:\n{details}")

    target = project["target"]
    for field in ("fabricLoaderVersion", "fabricApiVersion", "loomVersion", "geckolibVersion"):
        value = target.get(field)
        if value is not None and not _VERSION_PATTERN.fullmatch(value):
            raise ProjectValidationError(f"target.{field} contains unsupported characters")

    mod_id = project["project"]["modId"]
    creature_id = project["creature"]["id"]
    if mod_id in _JAVA_RESERVED_IDENTIFIERS:
        raise ProjectValidationError(f"modId is a Java reserved identifier: {mod_id}")
    if creature_id in _JAVA_RESERVED_IDENTIFIERS:
        raise ProjectValidationError(f"creature.id is a Java reserved identifier: {creature_id}")
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
