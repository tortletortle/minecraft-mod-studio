#!/usr/bin/env python3
"""Small standard-library client for the MMS Live Game Debugger loopback bridge."""

from __future__ import annotations

import argparse
import json
import math
import re
import socket
import uuid
from pathlib import Path
from typing import Any


MAX_LINE_BYTES = 8192
MAX_CONNECTION_FILE_BYTES = 4096
SUPPORTED_PROTOCOL = 1
TOKEN_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class BridgeError(RuntimeError):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate connection descriptor field")
        result[key] = value
    return result


class BridgeClient:
    def __init__(self, connection_file: str | Path, timeout: float = 5.0):
        path = Path(connection_file)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise BridgeError("Invalid bridge timeout")
        if path.is_symlink():
            raise BridgeError("Refusing a symbolic-link connection file")
        try:
            with path.open("rb") as stream:
                raw_config = stream.read(MAX_CONNECTION_FILE_BYTES + 1)
        except OSError as exc:
            raise BridgeError("Cannot read bridge connection file") from exc
        if len(raw_config) > MAX_CONNECTION_FILE_BYTES:
            raise BridgeError("Bridge connection file exceeds the size limit")
        try:
            config = json.loads(raw_config.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise BridgeError("Invalid bridge connection file") from exc
        required_fields = {"protocol", "host", "port", "token"}
        if not isinstance(config, dict):
            raise BridgeError("Invalid bridge connection fields")
        config_fields = set(config)
        if not required_fields.issubset(config_fields) or config_fields - required_fields - {"mod_version"}:
            raise BridgeError("Invalid bridge connection fields")
        mod_version = config.get("mod_version")
        if "mod_version" in config and (
            not isinstance(mod_version, str) or not 1 <= len(mod_version) <= 64
        ):
            raise BridgeError("Invalid bridge mod_version")
        self.mod_version: str | None = mod_version
        if type(config.get("protocol")) is not int or config["protocol"] != SUPPORTED_PROTOCOL:
            raise BridgeError("Unsupported bridge protocol")
        if config.get("host") != "127.0.0.1":
            raise BridgeError("Refusing a non-loopback bridge host")
        port = config.get("port")
        token = config.get("token")
        if type(port) is not int or not 1 <= port <= 65535:
            raise BridgeError("Invalid bridge port")
        if not isinstance(token, str) or TOKEN_PATTERN.fullmatch(token) is None:
            raise BridgeError("Invalid bridge token")

        self._socket = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self._socket.settimeout(timeout)
        self._reader = self._socket.makefile("rb")
        self._writer = self._socket.makefile("wb")
        try:
            self._send({"protocol": SUPPORTED_PROTOCOL, "token": token})
            handshake = self._read()
            if handshake.get("ok") is not True or type(handshake.get("protocol")) is not int or handshake["protocol"] != SUPPORTED_PROTOCOL:
                raise BridgeError(f"Bridge authentication failed: {handshake.get('error', 'unknown error')}")
            capabilities = handshake.get("capabilities")
            if not isinstance(capabilities, list) or any(not isinstance(item, str) for item in capabilities):
                raise BridgeError("Bridge returned invalid capabilities")
            self.capabilities = capabilities
        except Exception:
            self.close()
            raise

    def _send(self, value: dict[str, Any]) -> None:
        data = (json.dumps(value, separators=(",", ":")) + "\n").encode("utf-8")
        if len(data) > MAX_LINE_BYTES:
            raise BridgeError("Request exceeds protocol line limit")
        self._writer.write(data)
        self._writer.flush()

    def _read(self) -> dict[str, Any]:
        line = self._reader.readline(MAX_LINE_BYTES + 1)
        if not line:
            raise BridgeError("Bridge disconnected")
        if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
            raise BridgeError("Invalid or oversized bridge response")
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BridgeError("Bridge returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise BridgeError("Bridge response must be a JSON object")
        return value

    def request(self, operation: str, **arguments: Any) -> dict[str, Any]:
        if "id" in arguments or "command" in arguments:
            raise BridgeError("Reserved request fields cannot be overridden")
        if not isinstance(operation, str) or not operation:
            raise BridgeError("Command must be a non-empty string")
        request_id = str(uuid.uuid4())
        self._send({"id": request_id, "command": operation, **arguments})
        response = self._read()
        if response.get("id") != request_id:
            raise BridgeError("Response ID mismatch")
        if response.get("ok") is not True:
            raise BridgeError(str(response.get("error", "COMMAND_FAILED")))
        result = response.get("result")
        if not isinstance(result, dict):
            raise BridgeError("Bridge result must be a JSON object")
        return result

    def close(self) -> None:
        for stream_name in ("_reader", "_writer"):
            stream = getattr(self, stream_name, None)
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
                setattr(self, stream_name, None)
        sock = getattr(self, "_socket", None)
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
            self._socket = None

    def __enter__(self) -> "BridgeClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-file", required=True, type=Path)
    parser.add_argument(
        "--command",
        required=True,
        choices=("status", "move", "look", "stop", "entities", "inspect_entity",
                  "entity_attributes", "set_entity_attribute", "reset_entity_attributes",
                  "trigger_animation", "block"),
    )
    parser.add_argument("--args", default="{}", help="JSON object containing command arguments")
    args = parser.parse_args()

    try:
        payload = json.loads(args.args)
        if not isinstance(payload, dict):
            raise BridgeError("--args must decode to a JSON object")
        with BridgeClient(args.connection_file) as bridge:
            result = bridge.request(args.command, **payload)
            print(json.dumps({"capabilities": bridge.capabilities, "result": result}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, BridgeError) as exc:
        parser.exit(2, f"Live Game Debugger error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
