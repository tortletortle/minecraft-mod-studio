#!/usr/bin/env python3
"""Expose the MMS Live Game Debugger to a local MCP client over stdio."""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Image
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
            "Read a scene snapshot before acting. Prefer mms_move_player_and_verify over raw movement: it "
            "returns before/after state and checks whether the requested game ticks elapsed. A transient "
            "control session can be authorized for at most ten minutes; its authorization tool itself "
            "must remain approval-gated. Movement is limited to 1–40 game ticks and automatically released. "
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

    authorization_lock = threading.Lock()
    authorization_state = {"expires_at": 0.0}

    def _require_transient_access(confirmed: bool, operation: str) -> None:
        if confirmed is True:
            return
        with authorization_lock:
            authorized = time.monotonic() < authorization_state["expires_at"]
        if not authorized:
            raise ToolError(
                f"TRANSIENT_AUTH_REQUIRED: authorize a short-lived control session or set confirm=true for {operation}."
            )

    @server.tool(annotations=read_only)
    def mms_game_status() -> JsonResult:
        """Read the current player's position, health, view, velocity, dimension and world tick."""
        return JsonResult(result=relay.request("status"))

    @server.tool(annotations=read_only)
    def mms_get_scene_snapshot(
        radius: Annotated[float, Field(ge=1.0, le=32.0, allow_inf_nan=False)] = 16.0,
    ) -> JsonResult:
        """Read one coherent snapshot of player state, nearby entities and blocks around the player."""
        return JsonResult(result=relay.request("scene_snapshot", radius=radius))

    @server.tool(annotations=read_only)
    def mms_capture_screenshot() -> Image:
        """Capture the current Minecraft client frame and return it as an image for visual inspection."""
        capture = relay.request("capture_screenshot")
        if capture.get("capture_requested") is not True or capture.get("file_name") != "capture.png":
            raise ToolError("SCREENSHOT_PROTOCOL_INVALID: the companion did not accept the capture request.")
        capture_id = capture.get("capture_id")
        if not isinstance(capture_id, str) or len(capture_id) != 36:
            raise ToolError("SCREENSHOT_PROTOCOL_INVALID: capture ID is invalid.")

        directory = relay.connection_file.parent
        metadata_path = directory / "capture.json"
        screenshot = directory / "capture.png"
        deadline = time.monotonic() + 10.0
        metadata: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            if metadata_path.is_symlink():
                raise ToolError("SCREENSHOT_PATH_REJECTED: capture metadata must not be a symbolic link.")
            if metadata_path.is_file():
                try:
                    if metadata_path.stat().st_size > 4096:
                        raise ToolError("SCREENSHOT_METADATA_INVALID: capture metadata exceeds its size limit.")
                    candidate = json.loads(metadata_path.read_text(encoding="utf-8"))
                except ToolError:
                    raise
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    candidate = None
                if isinstance(candidate, dict) and candidate.get("capture_id") == capture_id:
                    metadata = candidate
                    break
            time.sleep(0.05)

        if metadata is None:
            raise ToolError("SCREENSHOT_TIMEOUT: the asynchronous render-target capture did not finish in 10 seconds.")
        if metadata.get("error"):
            raise ToolError("SCREENSHOT_CAPTURE_FAILED: the Fabric client could not write the captured frame.")
        if screenshot.is_symlink() or not screenshot.is_file():
            raise ToolError("SCREENSHOT_NOT_AVAILABLE: the companion did not produce a regular capture file.")
        try:
            size = screenshot.stat().st_size
            with screenshot.open("rb") as stream:
                signature = stream.read(8)
        except OSError as exc:
            raise ToolError("SCREENSHOT_READ_FAILED: cannot read the captured frame.") from exc
        if size < 24 or size > 8 * 1024 * 1024 or signature != bytes((137, 80, 78, 71, 13, 10, 26, 10)):
            raise ToolError("SCREENSHOT_INVALID: expected a PNG between 24 bytes and 8 MiB.")
        return Image(path=screenshot)

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
    def mms_authorize_transient_controls(
        confirm: StrictBool = False,
        duration_seconds: Annotated[StrictInt, Field(ge=30, le=600)] = 120,
    ) -> JsonResult:
        """Explicitly authorize bounded movement, camera and animation controls for 30–600 seconds."""
        _require_confirmation(confirm, "authorizing transient Minecraft controls")
        expires_at = time.monotonic() + duration_seconds
        with authorization_lock:
            authorization_state["expires_at"] = expires_at
        return JsonResult(result={
            "authorized": True,
            "duration_seconds": duration_seconds,
            "expires_in_seconds": duration_seconds,
            "scope": ["bounded_player_movement", "camera_look", "generated_animation_trigger"],
            "persistent_entity_attribute_writes_require_per_call_confirmation": True,
        })

    @server.tool(annotations=transient)
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
        _require_transient_access(confirm, "bounded player movement")
        return JsonResult(result=relay.request(
            "move", forward=forward, strafe=strafe, ticks=ticks,
            jump=jump, sprint=sprint, sneak=sneak,
        ))

    @server.tool(annotations=transient)
    def mms_move_player_and_verify(
        forward: Annotated[float, Field(ge=-1.0, le=1.0, allow_inf_nan=False)],
        strafe: Annotated[float, Field(ge=-1.0, le=1.0, allow_inf_nan=False)],
        ticks: Annotated[StrictInt, Field(ge=1, le=40)] = 10,
        jump: StrictBool = False,
        sprint: StrictBool = False,
        sneak: StrictBool = False,
        confirm: StrictBool = False,
    ) -> JsonResult:
        """Move for a bounded duration, wait for game-tick completion, and return before/after position evidence."""
        _require_transient_access(confirm, "verified bounded player movement")
        before = relay.request("status")
        before_player = before.get("player")
        if not isinstance(before_player, dict) or "x" not in before_player or "y" not in before_player or "z" not in before_player:
            raise ToolError("STATUS_SCHEMA_INVALID: player position is unavailable.")
        if before.get("movement_active") is True:
            raise ToolError("MOVEMENT_ALREADY_ACTIVE: stop or wait for the current movement first.")
        start_tick = before.get("game_time")
        if isinstance(start_tick, bool) or not isinstance(start_tick, int):
            raise ToolError("STATUS_SCHEMA_INVALID: game_time is unavailable.")
        move_result = relay.request(
            "move", forward=forward, strafe=strafe, ticks=ticks,
            jump=jump, sprint=sprint, sneak=sneak,
        )
        deadline = time.monotonic() + min(12.0, max(3.0, ticks * 0.25 + 2.0))
        after = before
        elapsed_ticks = 0
        while time.monotonic() < deadline:
            time.sleep(0.05)
            after = relay.request("status")
            game_time = after.get("game_time")
            if isinstance(game_time, bool) or not isinstance(game_time, int):
                raise ToolError("STATUS_SCHEMA_INVALID: game_time disappeared during movement.")
            elapsed_ticks = max(0, game_time - start_tick)
            active = after.get("movement_active") is True
            if elapsed_ticks >= ticks and not active:
                break
            if not active and elapsed_ticks < ticks:
                break
        completed = elapsed_ticks >= ticks and after.get("movement_active") is False
        if not completed:
            try:
                relay.request("stop")
                after = relay.request("status")
            except ToolError:
                pass
            game_time = after.get("game_time")
            if isinstance(game_time, int) and not isinstance(game_time, bool):
                elapsed_ticks = max(0, game_time - start_tick)
        after_player = after.get("player")
        if not isinstance(after_player, dict):
            raise ToolError("STATUS_SCHEMA_INVALID: final player position is unavailable.")
        delta = {
            axis: float(after_player[axis]) - float(before_player[axis])
            for axis in ("x", "y", "z")
        }
        distance = math.sqrt(sum(value * value for value in delta.values()))
        return JsonResult(result={
            "command_accepted": move_result.get("accepted") is True,
            "movement_completed": completed,
            "movement_observed": distance > 0.05,
            "requested_ticks": ticks,
            "elapsed_game_ticks": elapsed_ticks,
            "position_delta": delta,
            "distance_moved_blocks": distance,
            "before": before,
            "after": after,
            "failure_reason": None if completed else (
                "MOVEMENT_INTERRUPTED" if after.get("movement_active") is False else "MOVEMENT_TIMEOUT"
            ),
        })

    @server.tool(annotations=transient)
    def mms_look_player(
        yaw: Annotated[float, Field(ge=-180.0, le=180.0, allow_inf_nan=False)],
        pitch: Annotated[float, Field(ge=-90.0, le=90.0, allow_inf_nan=False)],
        confirm: StrictBool = False,
    ) -> JsonResult:
        """Change the local test player's camera orientation; requires confirm=true."""
        _require_transient_access(confirm, "changing the player view")
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
        _require_transient_access(confirm, "triggering a generated mob animation")
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
