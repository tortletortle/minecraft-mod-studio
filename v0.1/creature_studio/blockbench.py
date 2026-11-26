from __future__ import annotations

import base64
import copy
import json
import struct
from pathlib import Path
from typing import Any


class BlockbenchImportError(ValueError):
    pass


def _vec3(value: Any, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise BlockbenchImportError(f"{label} must be a three-number array")
    try:
        result = [float(v) for v in value]
    except (TypeError, ValueError) as exc:
        raise BlockbenchImportError(f"{label} contains a non-number") from exc
    if not all(abs(v) <= 1024 for v in result):
        raise BlockbenchImportError(f"{label} exceeds the V0.1 coordinate limit")
    return result


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise BlockbenchImportError("The model texture is not a valid PNG")
    width, height = struct.unpack(">II", data[16:24])
    if not (1 <= width <= 2048 and 1 <= height <= 2048):
        raise BlockbenchImportError("Texture dimensions must be between 1 and 2048 pixels")
    return width, height


def _texture_bytes(texture: dict[str, Any], model_dir: Path) -> bytes:
    source = texture.get("source")
    if isinstance(source, str) and source.startswith("data:image/png;base64,"):
        try:
            data = base64.b64decode(source.split(",", 1)[1], validate=True)
        except ValueError as exc:
            raise BlockbenchImportError("Embedded PNG texture has invalid base64 data") from exc
    else:
        relative = texture.get("relative_path") or texture.get("path")
        if not isinstance(relative, str) or not relative:
            raise BlockbenchImportError("V0.1 requires one embedded PNG texture or a relative PNG path")
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise BlockbenchImportError("Texture paths must remain inside the model directory")
        resolved = (model_dir / candidate).resolve()
        if not resolved.is_relative_to(model_dir.resolve()):
            raise BlockbenchImportError("Texture path escapes the model directory")
        if not resolved.is_file():
            raise BlockbenchImportError(f"Texture file not found: {relative}")
        data = resolved.read_bytes()
    _png_dimensions(data)
    return data


def _is_zero_rotation(value: Any, label: str) -> None:
    rotation = _vec3(value or [0, 0, 0], label)
    if any(abs(v) > 1e-6 for v in rotation):
        raise BlockbenchImportError(
            f"{label} is rotated. V0.1 only accepts unrotated bones/cubes; "
            "the importer refuses lossy conversion."
        )


def import_bbmodel(path: str | Path) -> dict[str, Any]:
    model_path = Path(path).resolve()
    try:
        document = json.loads(model_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BlockbenchImportError(f"Cannot read Blockbench project: {exc}") from exc

    meta = document.get("meta") or {}
    if str(meta.get("format_version")) != "5.0":
        raise BlockbenchImportError(
            "V0.1 supports Blockbench .bbmodel format 5.0 only. "
            f"Found {meta.get('format_version')!r}."
        )
    if meta.get("model_format") not in {"free", "modded_entity"}:
        raise BlockbenchImportError(
            "V0.1 accepts Blockbench Generic Model or Modded Entity projects."
        )
    if meta.get("box_uv") is not True:
        raise BlockbenchImportError(
            "V0.1 currently requires box UV mode; per-face UV models are not silently flattened."
        )

    groups = document.get("groups") or []
    elements = document.get("elements") or []
    if not groups:
        raise BlockbenchImportError("The model must contain at least one bone/group")
    if not elements:
        raise BlockbenchImportError("The model must contain at least one cube")

    group_by_uuid = {item.get("uuid"): item for item in groups if item.get("uuid")}
    element_by_uuid = {item.get("uuid"): item for item in elements if item.get("uuid")}
    if len(group_by_uuid) != len(groups) or len(element_by_uuid) != len(elements):
        raise BlockbenchImportError("Every group and cube must have a unique UUID")

    group_parent: dict[str, str | None] = {}
    element_parent: dict[str, str] = {}
    group_order: list[str] = []
    seen_groups: set[str] = set()
    seen_elements: set[str] = set()

    def walk(nodes: list[Any], parent: str | None = None) -> None:
        for node in nodes:
            if isinstance(node, str):
                if node not in element_by_uuid:
                    raise BlockbenchImportError(f"Outliner references unknown cube UUID: {node}")
                if node in seen_elements:
                    raise BlockbenchImportError(f"Cube appears more than once in outliner: {node}")
                if parent is None:
                    raise BlockbenchImportError("Every cube must be inside a bone/group")
                seen_elements.add(node)
                element_parent[node] = parent
                continue
            if not isinstance(node, dict) or not isinstance(node.get("uuid"), str):
                raise BlockbenchImportError("Invalid Blockbench 5.0 outliner node")
            uid = node["uuid"]
            if uid not in group_by_uuid:
                raise BlockbenchImportError(f"Outliner references unknown group UUID: {uid}")
            if uid in seen_groups:
                raise BlockbenchImportError(f"Group appears more than once in outliner: {uid}")
            seen_groups.add(uid)
            group_order.append(uid)
            group_parent[uid] = parent
            children = node.get("children", [])
            if not isinstance(children, list):
                raise BlockbenchImportError(f"Group {uid} has invalid children")
            walk(children, uid)

    outliner = document.get("outliner")
    if not isinstance(outliner, list):
        raise BlockbenchImportError("Blockbench 5.0 outliner must be an array")
    walk(outliner)
    if seen_groups != set(group_by_uuid):
        raise BlockbenchImportError("Some groups are missing from the outliner")
    if seen_elements != set(element_by_uuid):
        raise BlockbenchImportError("Some cubes are missing from the outliner")

    origins: dict[str, list[float]] = {}
    bones: list[dict[str, Any]] = []
    for uid in group_order:
        raw = group_by_uuid[uid]
        origin = _vec3(raw.get("origin", [0, 0, 0]), f"group {uid}.origin")
        _is_zero_rotation(raw.get("rotation", [0, 0, 0]), f"group {uid}.rotation")
        parent = group_parent[uid]
        parent_origin = origins[parent] if parent else [0.0, 0.0, 0.0]
        pivot = [origin[i] - parent_origin[i] for i in range(3)]
        origins[uid] = origin
        bones.append({
            "uuid": uid,
            "name": str(raw.get("name") or "bone"),
            "parent": parent,
            "origin": origin,
            "pivot": pivot,
            "raw": copy.deepcopy(raw),
            "cubes": []
        })

    bone_by_uuid = {bone["uuid"]: bone for bone in bones}
    for raw in elements:
        uid = raw["uuid"]
        if raw.get("type", "cube") != "cube":
            raise BlockbenchImportError(f"Unsupported element type for V0.1: {raw.get('type')}")
        _is_zero_rotation(raw.get("rotation", [0, 0, 0]), f"cube {uid}.rotation")
        start = _vec3(raw.get("from"), f"cube {uid}.from")
        end = _vec3(raw.get("to"), f"cube {uid}.to")
        size = [end[i] - start[i] for i in range(3)]
        if any(v <= 0 or v > 64 for v in size):
            raise BlockbenchImportError(f"Cube {uid} has invalid dimensions")
        parent = element_parent[uid]
        origin = origins[parent]
        local_from = [start[i] - origin[i] for i in range(3)]
        uv = raw.get("uv_offset", raw.get("uv"))
        if uv is None:
            north = (raw.get("faces") or {}).get("north") or {}
            face_uv = north.get("uv", [0, 0, 0, 0])
            uv = face_uv[:2]
        if not isinstance(uv, list) or len(uv) < 2:
            raise BlockbenchImportError(f"Cube {uid} has no supported box UV offset")
        uv = [int(round(float(uv[0]))), int(round(float(uv[1])))]
        if min(uv) < 0:
            raise BlockbenchImportError(f"Cube {uid} has negative UV coordinates")
        bone_by_uuid[parent]["cubes"].append({
            "uuid": uid,
            "name": str(raw.get("name") or "cube"),
            "from": start,
            "to": end,
            "localFrom": local_from,
            "size": size,
            "uv": uv,
            "raw": copy.deepcopy(raw)
        })

    textures = document.get("textures") or []
    if len(textures) != 1:
        raise BlockbenchImportError(
            f"V0.1 supports exactly one texture; found {len(textures)}."
        )
    texture_raw = copy.deepcopy(textures[0])
    texture_data = _texture_bytes(texture_raw, model_path.parent)
    width, height = _png_dimensions(texture_data)
    declared_width = int(texture_raw.get("uv_width", texture_raw.get("width", width)))
    declared_height = int(texture_raw.get("uv_height", texture_raw.get("height", height)))
    if (declared_width, declared_height) != (width, height):
        raise BlockbenchImportError(
            "The embedded PNG dimensions do not match the Blockbench UV dimensions."
        )

    return {
        "format": "blockbench_bbmodel",
        "formatVersion": "5.0",
        "modelFormat": meta["model_format"],
        "boxUv": True,
        "textureSize": [width, height],
        "bones": bones,
        "texture": {
            "name": str(texture_raw.get("name") or "entity"),
            "fileName": "entity.png",
            "pngBase64": base64.b64encode(texture_data).decode("ascii"),
            "raw": texture_raw
        },
        "animations": copy.deepcopy(document.get("animations") or []),
        "sourceMeta": copy.deepcopy(meta),
        "sourceResolution": copy.deepcopy(document.get("resolution") or {"width": width, "height": height}),
        "sourceDocument": copy.deepcopy(document)
    }


def export_bbmodel(model: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    document = copy.deepcopy(model.get("sourceDocument") or {})
    meta = copy.deepcopy(model.get("sourceMeta") or {})
    meta.update({"format_version": "5.0", "model_format": model.get("modelFormat", "free"), "box_uv": True})
    document["meta"] = meta
    width, height = model["textureSize"]
    document["resolution"] = {"width": width, "height": height}

    bones = model["bones"]
    groups = []
    bone_ids = {bone["uuid"] for bone in bones}
    children: dict[str | None, list[dict[str, Any]]] = {None: []}
    for bone in bones:
        parent = bone["parent"]
        if parent is not None and parent not in bone_ids:
            raise BlockbenchImportError(f"Unknown parent bone: {parent}")
        children.setdefault(parent, []).append(bone)
        children.setdefault(bone["uuid"], [])
        raw = copy.deepcopy(bone.get("raw") or {})
        raw.update({
            "uuid": bone["uuid"],
            "name": bone["name"],
            "origin": bone["origin"],
            "rotation": [0, 0, 0]
        })
        groups.append(raw)

    elements = []
    for bone in bones:
        for cube in bone["cubes"]:
            raw = copy.deepcopy(cube.get("raw") or {})
            raw.update({
                "uuid": cube["uuid"],
                "name": cube["name"],
                "type": "cube",
                "from": cube["from"],
                "to": cube["to"],
                "origin": bone["origin"],
                "rotation": [0, 0, 0],
                "uv_offset": cube["uv"]
            })
            elements.append(raw)

    def outliner_node(bone: dict[str, Any]) -> dict[str, Any]:
        nested: list[Any] = [cube["uuid"] for cube in bone["cubes"]]
        nested.extend(outliner_node(child) for child in children[bone["uuid"]])
        return {"uuid": bone["uuid"], "isOpen": True, "children": nested}

    document["groups"] = groups
    document["elements"] = elements
    document["outliner"] = [outliner_node(bone) for bone in children[None]]
    texture = copy.deepcopy(model["texture"].get("raw") or {})
    texture.update({
        "name": model["texture"]["name"],
        "uv_width": width,
        "uv_height": height,
        "width": width,
        "height": height,
        "source": "data:image/png;base64," + model["texture"]["pngBase64"],
        "internal": True
    })
    document["textures"] = [texture]
    document["animations"] = copy.deepcopy(model.get("animations") or [])

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
