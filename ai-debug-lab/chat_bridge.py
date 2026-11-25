"""Local HTTP bridge from Minecraft chat to a local model or a desktop MCP session."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
import time
from typing import Any
from urllib.parse import urlsplit

from runtime_cache import CacheLockTimeout, FileLock, RuntimeCacheError


DESCRIPTOR_NAME = "mms-chat-bridge.json"
DIAGNOSE_PATH = "/v1/diagnose"
DESKTOP_NEXT_PATH = "/v1/desktop/next"
DESKTOP_REPLY_PATH = "/v1/desktop/reply"
DESKTOP_QUESTION_TIMEOUT = 75.0
MAX_DESKTOP_POLL = 20
MODEL_PATH = "/v1/chat/completions"
MAX_REQUEST_BYTES = 16 * 1024
MAX_DESCRIPTOR_BYTES = 4096
MAX_MODEL_RESPONSE_BYTES = 64 * 1024
MAX_REPLY_LENGTH = 600
RESOURCE_ID = re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+")
PROPERTY_NAME = re.compile(r"[a-z0-9_]+")
PROPERTY_VALUE = re.compile(r"[a-z0-9_.-]+")
BLOCK_FLAGS = {"requires_correct_tool_for_drops", "held_item_correct_for_drops"}
REQUEST_ID = re.compile(r"[a-f0-9]{32}")
RELAY_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")

SYSTEM_PROMPT = (
    "You are a Minecraft Java Edition debugging assistant. Answer the player's question in its language. "
    "Use the supplied read-only evidence about the target, held item and dimension. "
    "Distinguish observations from possible explanations, and suggest one quick check if useful. "
    "If the evidence is insufficient, say so. Do not claim to have run commands, "
    "changed the world, or seen other world data. Reply in at most three short sentences."
)


class ModelUnavailable(Exception):
    """The loopback model did not supply a valid text reply."""


class DesktopUnavailable(Exception):
    """The desktop relay stopped before replying."""


def _resource_id(value: Any) -> bool:
    return isinstance(value, str) and len(value) <= 256 and RESOURCE_ID.fullmatch(value) is not None


def validate_request(payload: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, dict) or payload.keys() != {"question", "context"}:
        raise ValueError("expected question and context")
    question, context = payload["question"], payload["context"]
    if not isinstance(question, str) or len(question) > 320 or not question.strip():
        raise ValueError("expected a nonempty question of at most 320 characters")
    question.encode("utf-8")  # JSON can escape an invalid Unicode surrogate.
    if not isinstance(context, dict) or not _resource_id(context.get("dimension")):
        raise ValueError("expected a dimension identifier")

    held, target = context.get("held"), context.get("target")
    if not isinstance(held, dict) or held.keys() != {"id", "count"} or not _resource_id(held["id"]):
        raise ValueError("expected held item evidence")
    if type(held["count"]) is not int or not 0 <= held["count"] <= 2_147_483_647:
        raise ValueError("invalid held item count")

    base_context = {"dimension", "held", "target"}
    if not isinstance(target, dict):
        raise ValueError("expected target evidence")
    kind = target.get("kind")
    if kind == "miss" and target.keys() == {"kind"} and context.keys() == base_context:
        return question.strip(), context
    if kind == "entity" and target.keys() == {"kind", "id"} and context.keys() == base_context:
        if _resource_id(target["id"]):
            return question.strip(), context
    if kind != "block" or target.keys() != {"kind", "id", "properties"} or not _resource_id(target["id"]):
        raise ValueError("invalid target evidence")
    if context.keys() != base_context | BLOCK_FLAGS or any(type(context[key]) is not bool for key in BLOCK_FLAGS):
        raise ValueError("expected block tool evidence")
    properties = target["properties"]
    if not isinstance(properties, dict) or len(properties) > 64:
        raise ValueError("invalid block properties")
    for key, value in properties.items():
        if (len(key) > 64 or not PROPERTY_NAME.fullmatch(key) or not isinstance(value, str)
                or len(value) > 128 or not PROPERTY_VALUE.fullmatch(value)):
            raise ValueError("invalid block property")
    return question.strip(), context


class LocalModel:
    def __init__(self, url: str, model: str, timeout: float = 90.0):
        invalid_url = "--model-url must be a numeric loopback HTTP URL ending in /v1/chat/completions"
        try:
            endpoint = urlsplit(url)
            host = endpoint.hostname or ""
            port = endpoint.port if endpoint.port is not None else 80
            loopback = ipaddress.ip_address(host).is_loopback and "%" not in host
        except ValueError as exc:
            raise ValueError(invalid_url) from exc
        if (not loopback or endpoint.scheme != "http" or endpoint.path != MODEL_PATH
                or endpoint.username is not None or endpoint.password is not None
                or endpoint.query or endpoint.fragment or not 1 <= port <= 65535):
            raise ValueError(invalid_url)
        if not model.strip() or len(model) > 256:
            raise ValueError("--model must be a nonempty local model name of at most 256 characters")
        self.host = host
        self.port = port
        self.model = model.strip()
        self.timeout = timeout

    def diagnose(self, question: str, context: dict[str, Any]) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"question": question, "context": context}, ensure_ascii=False)},
            ],
            "stream": False,
            "max_tokens": 256,
            "temperature": 0.1,
        }
        # Direct HTTPConnection bypasses environment proxies and does not follow redirects.
        connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            connection.request("POST", MODEL_PATH, body=json.dumps(payload).encode("utf-8"),
                               headers={"Content-Type": "application/json", "Accept": "application/json"})
            with connection.getresponse() as response:
                if response.status != 200:
                    raise ModelUnavailable(f"Local model returned HTTP {response.status}")
                body = response.read(MAX_MODEL_RESPONSE_BYTES + 1)
                if len(body) > MAX_MODEL_RESPONSE_BYTES:
                    raise ModelUnavailable("Local model response exceeded size limit")
            reply = json.loads(body)["choices"][0]["message"]["content"]
            if not isinstance(reply, str) or not reply.strip():
                raise ModelUnavailable("Local model did not return text")
            reply.encode("utf-8")
            reply = " ".join(reply.split())
            if len(reply) > MAX_REPLY_LENGTH:
                reply = reply[:MAX_REPLY_LENGTH - 1].rstrip() + "…"
            return reply
        except TimeoutError:
            raise
        except (OSError, http.client.HTTPException, ValueError, KeyError, IndexError, TypeError, RecursionError) as exc:
            raise ModelUnavailable("Invalid or unavailable local model response") from exc
        finally:
            connection.close()


@dataclass
class PendingQuestion:
    id: str
    question: str
    context: dict[str, Any]
    deadline: float
    owner: str | None = None
    reply: str | None = None


class DesktopRelay:
    """Hold one in-flight game request until the claiming MCP session replies."""

    def __init__(self, timeout: float = DESKTOP_QUESTION_TIMEOUT):
        self.timeout = timeout
        self.condition = threading.Condition()
        self.pending: PendingQuestion | None = None
        self.closed = False

    def diagnose(self, question: str, context: dict[str, Any]) -> str:
        pending = PendingQuestion(secrets.token_hex(16), question, context, time.monotonic() + self.timeout)
        with self.condition:
            if self.closed:
                raise DesktopUnavailable
            self.pending = pending
            self.condition.notify_all()
            try:
                while pending.reply is None:
                    remaining = pending.deadline - time.monotonic()
                    if self.closed:
                        raise DesktopUnavailable
                    if remaining <= 0:
                        raise TimeoutError
                    self.condition.wait(remaining)
                return pending.reply
            finally:
                self.pending = None
                self.condition.notify_all()

    def next(self, owner: str, wait_seconds: int) -> dict[str, Any] | None:
        deadline = time.monotonic() + wait_seconds
        with self.condition:
            while not self.closed:
                pending = self.pending
                now = time.monotonic()
                if (pending is not None and now < pending.deadline and pending.reply is None
                        and pending.owner in (None, owner)):
                    pending.owner = owner
                    return {"request_id": pending.id, "question": pending.question, "context": pending.context}
                remaining = deadline - now
                if remaining <= 0:
                    return None
                self.condition.wait(remaining)
            raise DesktopUnavailable

    def deliver(self, owner: str, request_id: str, reply: str) -> bool:
        with self.condition:
            pending = self.pending
            if (self.closed or pending is None or pending.owner != owner or pending.id != request_id
                    or pending.reply is not None or time.monotonic() >= pending.deadline):
                return False
            pending.reply = reply
            self.condition.notify_all()
            return True

    def close(self) -> None:
        with self.condition:
            self.closed = True
            self.condition.notify_all()


class BridgeServer(ThreadingHTTPServer):
    def __init__(self, backend: LocalModel | DesktopRelay, token: str):
        self.backend = backend
        self.token = f"Bearer {token}".encode("ascii")
        self.diagnosing = threading.Lock()
        self.polling = threading.Lock()
        super().__init__(("127.0.0.1", 0), DiagnoseHandler)


class DiagnoseHandler(BaseHTTPRequestHandler):
    server: BridgeServer
    timeout = 5.0

    def log_message(self, format: str, *args: Any) -> None:
        # The token and request body never belong in logs.
        pass

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionError, TimeoutError):
            # The player may exit the game while the model is still responding.
            pass

    def do_POST(self) -> None:
        self.close_connection = True
        desktop = isinstance(self.server.backend, DesktopRelay)
        if self.path != DIAGNOSE_PATH and (not desktop or self.path not in (DESKTOP_NEXT_PATH, DESKTOP_REPLY_PATH)):
            self._json(404, {"error": "诊断接口不存在，请更新游戏端与桥接服务。"})
            return
        authorization = self.headers.get_all("Authorization", [])
        if len(authorization) != 1 or not hmac.compare_digest(authorization[0].encode("latin-1"), self.server.token):
            self._json(401, {"error": "诊断连接验证失败，请重启桥接服务后重试。"})
            return
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if (self.headers.get("Transfer-Encoding") is not None or len(lengths) != 1
                    or not re.fullmatch(r"[0-9]{1,10}", lengths[0])
                    or self.headers.get_content_type() != "application/json"):
                raise ValueError("invalid request headers")
            length = int(lengths[0])
            if length > MAX_REQUEST_BYTES:
                self._json(413, {"error": "诊断请求过大，请缩短问题后重试。"})
                return
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("incomplete request body")
            payload = json.loads(body.decode("utf-8"))
        except TimeoutError:
            self._json(408, {"error": "读取诊断请求超时，请重新发送。"})
            return
        except ConnectionError:
            return
        except (ValueError, RecursionError):
            self._json(400, {"error": "诊断请求无效，请用游戏内 /mms ask 输入 1 到 320 个字符。"})
            return

        if self.path != DIAGNOSE_PATH:
            self._desktop(payload)
            return
        try:
            question, context = validate_request(payload)
        except ValueError:
            self._json(400, {"error": "诊断请求无效，请用游戏内 /mms ask 输入 1 到 320 个字符。"})
            return
        if not self.server.diagnosing.acquire(blocking=False):
            error = "请等当前诊断结束后再试。" if desktop else "本地模型正在回答，请等当前诊断结束后再试。"
            self._json(429, {"error": error})
            return
        try:
            reply = self.server.backend.diagnose(question, context)
        except TimeoutError:
            error = "桌面对话未及时回复。请先在桌面对话中等待游戏问题，再提问。" if desktop else (
                "本地模型回答超时，请检查模型状态或缩短问题后重试。")
            self._json(504, {"error": error})
        except DesktopUnavailable:
            self._json(503, {"error": "桌面诊断桥已停止，请重启桥接服务后重试。"})
        except ModelUnavailable:
            self._json(502, {"error": "无法取得本地模型回复，请确认推理服务与模型已启动。"})
        else:
            self._json(200, {"reply": reply})
        finally:
            self.server.diagnosing.release()

    def _desktop(self, payload: Any) -> None:
        relay = self.server.backend
        assert isinstance(relay, DesktopRelay)
        owner = payload.get("owner") if isinstance(payload, dict) else None
        if not isinstance(owner, str) or not RELAY_TOKEN.fullmatch(owner):
            self._json(400, {"error": "Invalid desktop request."})
            return
        if self.path == DESKTOP_NEXT_PATH:
            wait = payload.get("wait_seconds")
            if payload.keys() != {"owner", "wait_seconds"} or type(wait) is not int or not 0 <= wait <= MAX_DESKTOP_POLL:
                self._json(400, {"error": "Invalid desktop wait."})
                return
            if not self.server.polling.acquire(blocking=False):
                self._json(429, {"error": "A desktop session is already polling."})
                return
            try:
                question = relay.next(owner, wait)
            except DesktopUnavailable:
                self._json(503, {"error": "The desktop relay stopped."})
            else:
                self._json(200, {"question": question})
            finally:
                self.server.polling.release()
            return

        request_id, reply = payload.get("request_id"), payload.get("reply")
        if (payload.keys() != {"owner", "request_id", "reply"}
                or not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id)
                or not isinstance(reply, str) or not reply.strip() or len(reply) > MAX_REPLY_LENGTH):
            self._json(400, {"error": "Invalid desktop reply."})
            return
        try:
            reply.encode("utf-8")
        except UnicodeError:
            self._json(400, {"error": "Invalid characters in desktop reply."})
            return
        if not relay.deliver(owner, request_id, " ".join(reply.split())):
            self._json(409, {"error": "The request expired, was answered, or belongs to another MCP session."})
            return
        self._json(200, {"delivered": True})


def _publish_descriptor(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as file:
        temporary_path = Path(file.name)
        try:
            file.write(data)
            file.close()
            os.replace(temporary_path, path)
        finally:
            file.close()
            temporary_path.unlink(missing_ok=True)


@contextmanager
def chat_bridge(game_dir: Path, model: LocalModel | DesktopRelay):
    descriptor = game_dir / "config" / DESCRIPTOR_NAME
    token = secrets.token_urlsafe(32)
    with FileLock(descriptor.with_suffix(".lock"), timeout=0), BridgeServer(model, token) as server:
        data = json.dumps({"version": 1, "port": server.server_port, "token": token}).encode("utf-8")
        _publish_descriptor(descriptor, data)
        try:
            yield server
        finally:
            if isinstance(model, DesktopRelay):
                model.close()
            try:
                with descriptor.open("rb") as file:
                    owns_descriptor = file.read(len(data) + 1) == data
                if owns_descriptor:
                    descriptor.unlink()
            except FileNotFoundError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, required=True, help="Minecraft instance directory")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--desktop-mcp", action="store_true", help="wait for a question and reply through the desktop MCP server")
    mode.add_argument("--model-url", help="local HTTP /v1/chat/completions URL on a numeric loopback IP")
    parser.add_argument("--model", help="local model name advertised by the inference server")
    args = parser.parse_args()
    if args.desktop_mcp and args.model is not None:
        parser.error("--model applies only with --model-url")
    if not args.desktop_mcp and args.model is None:
        parser.error("--model is required with --model-url")
    try:
        model = DesktopRelay() if args.desktop_mcp else LocalModel(args.model_url, args.model)
        game_dir = args.game_dir.expanduser().resolve(strict=True)
        if not game_dir.is_dir():
            raise ValueError("--game-dir must be an existing Minecraft instance directory")
        with chat_bridge(game_dir, model) as server:
            suffix = " (desktop MCP)" if args.desktop_mcp else ""
            print(f"Minecraft chat bridge listening on 127.0.0.1:{server.server_port}{suffix}", flush=True)
            server.serve_forever()
    except CacheLockTimeout:
        parser.exit(1, "A chat bridge already owns this Minecraft instance.\n")
    except (OSError, RuntimeCacheError, ValueError) as exc:
        parser.exit(1, f"Cannot start or stop Minecraft chat bridge: {exc}\n")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
