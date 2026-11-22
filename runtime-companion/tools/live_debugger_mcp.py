#!/usr/bin/env python3
"""Expose the MMS Live Game Debugger to a local MCP client over stdio."""

from __future__ import annotations

import argparse
import math
import threading
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, StrictBool, StrictInt

from live_debugger_client import BridgeClient, BridgeError


UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
ANIMATION_PATTERN = r"^[A-Za-z0-9_.:-]{1,48}$"
ATTRIBUTE_LIMITS = {
    "max_health": (1.0, 1024.0),
    "attack_damage": (0.0, 256.0),
    "movement_speed": (0.0, 4.0),
}


class JsonResult(BaseModel):
    result: dict[str, Any]


class LiveDebuggerRelay:
    """Open one short-lived authenticated connection for each tool call."""

    def __init__(self, connection_file: Path):
        self.connection_file = connection_file
        self.lock = threading.Lock()

    def request(self, command: str, **arguments: Any) -> dict[str, Any]:
        # The Fabric companion accepts one agent connection at a time. Serialize
        # MCP calls and close each socket promptly so shutdown/restart is clean.
        with self.lock:
            try:
                with BridgeClient(self.connection_file) as bridge:
                    if command not in bridge.capabilities:
                        raise ToolError(f"Live Game Debugger does not advertise capability: {command}")
                    return bridge.request(command, **arguments)
            except ToolError:
                raise
            except BridgeError as exc:
                raise ToolError(f"Live Game Debugger rejected the request: {exc}") from exc
            except (OSError, ValueError) as exc:
                raise ToolError(
                    "Live Game Debugger is unavailable. Confirm Minecraft is running with the "
                    "companion installed and that the connection file belongs to this game launch."
                ) from exc


def _require_confirmation(confirmed: bool, operation: str) -> None:
    if confirmed is not True:
        raise ToolError(f"CONFIRM_REQUIRED: set confirm=true to authorize {operation}.")


def build_server(connection_file: Path) -> MCPServer:
    relay = LiveDebuggerRelay(connection_file)
    server = MCPServer(
        "Minecraft Mod Studio Live Debugger",
        instructions=(
            "This server controls one local Minecraft Java 26.2 Fabric single-player test client. "
            "Read status and nearby evidence before taking action. Movement is limited to 1–40 game "
            "ticks and automatically released. Player movement, camera changes, animation triggers, "
            "and entity attribute writes are distinct operations. Persistent base-attribute changes "
            "may be saved with the world; use only a disposable Creative test world and obtain explicit "
            "operator authorization before changing them. Reset restores only the three supported "
            "generated Rig defaults. Never claim a command succeeded unless its tool result confirms it. "
            "There is no arbitrary command, Java execution, block editing, entity spawning, or multiplayer control."
        ),
    )

    read_only = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
    transient = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
    controlled = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)

    @server.tool(annotations=read_only)
    def mms_game_status() -> JsonResult:
        """Read the current player's position, health, view, velocity, dimension and world tick."""
        return JsonResult(result=relay.request("status"))

    @server.tool(annotations=read_only)
    def mms_list_nearby_entities(
        radius: Annotated[float, Field(ge=1.0, le=32.0, allow_inf_nan=False)] = 16.0,
    ) -> JsonResult:
        """List up to 50 loaded entities within a radius of 1–32 blocks."""
        return JsonResult(result=relay.request("entities", radius=radius))

    @server.tool(annotations=read_only)
    def mms_inspect_entity(
        uuid: Annotated[str, Field(pattern=UUID_PATTERN)],
    ) -> JsonResult:
        """Read details for one loaded entity by UUID; this does not modify the entity."""
        return JsonResult(result=relay.request("inspect_entity", uuid=uuid))

    @server.tool(annotations=read_only)
    def mms_inspect_block(
        x: StrictInt,
        y: StrictInt,
        z: StrictInt,
    ) -> JsonResult:
        """Read the registry ID and basic state of one block within 64 blocks of the player."""
        return JsonResult(result=relay.request("block", x=x, y=y, z=z))

    @server.tool(annotations=read_only)
    def mms_read_entity_attributes(
        uuid: Annotated[str, Field(pattern=UUID_PATTERN)],
    ) -> JsonResult:
        """Read server-authoritative base/effective values for a generated Studio mob."""
        return JsonResult(result=relay.request("entity_attributes", uuid=uuid))

    @server.tool(annotations=controlled)
    def mms_move_player(
        forward: Annotated[float, Field(ge=-1.0, le=1.0, allow_inf_nan=False)],
        strafe: Annotated[float, Field(ge=-1.0, le=1.0, allow_inf_nan=False)],
        ticks: Annotated[StrictInt, Field(ge=1, le=40)] = 10,
        jump: StrictBool = False,
        sprint: StrictBool = False,
        sneak: StrictBool = False,
        confirm: StrictBool = False,
    ) -> JsonResult:
        """Move the player for at most 40 game ticks; requires confirm=true and auto-releases input."""
        _require_confirmation(confirm, "bounded player movement")
        return JsonResult(result=relay.request(
            "move", forward=forward, strafe=strafe, ticks=ticks,
            jump=jump, sprint=sprint, sneak=sneak,
        ))

    @server.tool(annotations=transient)
    def mms_look_player(
        yaw: Annotated[float, Field(ge=-180.0, le=180.0, allow_inf_nan=False)],
        pitch: Annotated[float, Field(ge=-90.0, le=90.0, allow_inf_nan=False)],
        confirm: StrictBool = False,
    ) -> JsonResult:
        """Change the local test player's camera orientation; requires confirm=true."""
        _require_confirmation(confirm, "changing the player view")
        return JsonResult(result=relay.request("look", yaw=yaw, pitch=pitch))

    @server.tool(annotations=transient)
    def mms_stop_player() -> JsonResult:
        """Immediately release movement keys owned by the debugger; safe to call without confirmation."""
        return JsonResult(result=relay.request("stop"))

    @server.tool(annotations=controlled)
    def mms_set_entity_attribute(
        uuid: Annotated[str, Field(pattern=UUID_PATTERN)],
        attribute: Literal["max_health", "attack_damage", "movement_speed"],
        value: Annotated[float, Field(ge=0.0, le=1024.0, allow_inf_nan=False)],
        confirm: StrictBool = False,
    ) -> JsonResult:
        """Change one allowlisted generated-mob base attribute; requires confirm=true and a disposable world."""
        _require_confirmation(confirm, "changing a generated mob base attribute")
        minimum, maximum = ATTRIBUTE_LIMITS[attribute]
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise ToolError(f"ATTRIBUTE_VALUE_OUT_OF_RANGE: {attribute} must be between {minimum} and {maximum}.")
        return JsonResult(result=relay.request(
            "set_entity_attribute", uuid=uuid, attribute=attribute, value=value, confirm=True,
        ))

    @server.tool(annotations=controlled)
    def mms_reset_entity_attributes(
        uuid: Annotated[str, Field(pattern=UUID_PATTERN)],
        confirm: StrictBool = False,
    ) -> JsonResult:
        """Restore max health, attack damage and movement speed from the generated Rig defaults; requires confirm=true."""
        _require_confirmation(confirm, "resetting generated mob attributes")
        return JsonResult(result=relay.request("reset_entity_attributes", uuid=uuid, confirm=True))

    @server.tool(annotations=transient)
    def mms_trigger_animation(
        uuid: Annotated[str, Field(pattern=UUID_PATTERN)],
        animation_id: Annotated[str, Field(pattern=ANIMATION_PATTERN)],
        confirm: StrictBool = False,
    ) -> JsonResult:
        """Trigger one named animation on a generated Studio mob; requires confirm=true."""
        _require_confirmation(confirm, "triggering a generated mob animation")
        return JsonResult(result=relay.request(
            "trigger_animation", uuid=uuid, animation_id=animation_id,
        ))

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--connection-file",
        type=Path,
        required=True,
        help="connection.json created by the running MMS Live Game Debugger companion",
    )
    args = parser.parse_args()
    connection_file = args.connection_file.expanduser()
    if not connection_file.is_file():
        parser.error("--connection-file must point to the existing companion connection.json")
    build_server(connection_file).run(transport="stdio")


if __name__ == "__main__":
    main()
