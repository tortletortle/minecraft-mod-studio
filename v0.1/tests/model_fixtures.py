from __future__ import annotations

import copy
import json
from pathlib import Path


def write_duplicate_sibling_bbmodel(source: Path, destination: Path) -> Path:
    document = json.loads(source.read_text(encoding="utf-8"))
    body = next(group for group in document["groups"] if group["name"] == "body")
    duplicate_group = copy.deepcopy(body)
    duplicate_group["uuid"] = "77777777-7777-4777-8777-777777777777"
    duplicate_group["origin"] = [2, 4, 0]

    body_cube = next(element for element in document["elements"] if element["name"] == "Body Cube")
    duplicate_cube = copy.deepcopy(body_cube)
    duplicate_cube["uuid"] = "88888888-8888-4888-8888-888888888888"
    duplicate_cube["name"] = "Duplicate Body Cube"
    duplicate_cube["from"] = [0, 0, -1]
    duplicate_cube["to"] = [4, 2, 1]
    duplicate_cube["origin"] = [2, 4, 0]
    duplicate_cube["uv_offset"] = [32, 32]

    document["groups"].append(duplicate_group)
    document["elements"].append(duplicate_cube)
    root_uuid = next(group["uuid"] for group in document["groups"] if group["name"] == "root")
    root_node = next(
        node for node in document["outliner"]
        if isinstance(node, dict) and node["uuid"] == root_uuid
    )
    root_node["children"].append({
        "uuid": duplicate_group["uuid"],
        "isOpen": True,
        "children": [duplicate_cube["uuid"]],
    })
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return destination
