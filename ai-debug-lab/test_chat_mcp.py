import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

try:
    from mcp import Client, StdioServerParameters
except ModuleNotFoundError as exc:
    if exc.name != "mcp":
        raise
    raise unittest.SkipTest("optional MCP SDK is not installed") from exc

from chat_bridge import (
    DESCRIPTOR_NAME,
    DESKTOP_NEXT_PATH,
    DesktopRelay,
    chat_bridge,
)
from test_chat_bridge import PAYLOAD, REPLY, model_fixture, request, running


@contextmanager
def isolated_relay(backend):
    with TemporaryDirectory() as temporary:
        game_dir = Path(temporary)
        with chat_bridge(game_dir, backend) as server, running(server):
            descriptor = json.loads((game_dir / "config" / DESCRIPTOR_NAME).read_text(encoding="utf-8"))
            yield game_dir, descriptor


def stdio(game_dir):
    script = Path(__file__).with_name("chat_mcp.py").resolve()
    return Client(StdioServerParameters(command=sys.executable, args=["-B", str(script), "--game-dir", str(game_dir)]))


class DesktopRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_game_question_round_trip_over_mcp_subprocess(self):
        with isolated_relay(DesktopRelay(timeout=6)) as (game_dir, descriptor):
            async with stdio(game_dir) as client:
                self.assertEqual({tool.name for tool in (await client.list_tools()).tools},
                                 {"next_game_question", "reply_to_game"})
                idle = await client.call_tool("next_game_question", {"wait_seconds": 0})
                self.assertFalse(idle.is_error)
                self.assertIsNone(idle.structured_content.get("question"))
                question_call = asyncio.create_task(client.call_tool("next_game_question", {"wait_seconds": 2}))
                game = asyncio.create_task(asyncio.to_thread(request, descriptor))
                received = await question_call
                self.assertFalse(received.is_error)
                question = received.structured_content["question"]
                request_id = question["request_id"]
                self.assertRegex(request_id, r"^[a-f0-9]{32}$")
                self.assertEqual({key: question[key] for key in PAYLOAD}, PAYLOAD)
                self.assertNotIn(descriptor["token"], json.dumps(question))
                self.assertEqual(set(question), {"request_id", "question", "context"})
                busy, _ = await asyncio.to_thread(request, descriptor)
                self.assertEqual(busy, 429)
                wrong_id = await client.call_tool("reply_to_game", {"request_id": "0" * 32, "reply": REPLY})
                self.assertTrue(wrong_id.is_error)
                answer = await client.call_tool("reply_to_game", {"request_id": request_id, "reply": REPLY})
                self.assertFalse(answer.is_error)
                self.assertEqual(answer.structured_content, {"delivered": True})
                self.assertEqual(await game, (200, {"reply": REPLY}))
                replay = await client.call_tool("reply_to_game", {"request_id": request_id, "reply": REPLY})
                self.assertTrue(replay.is_error)

    async def test_expiration_and_claim_ownership(self):
        with isolated_relay(DesktopRelay(timeout=1.25)) as (game_dir, descriptor):
            async with stdio(game_dir) as owner, stdio(game_dir) as other:
                game = asyncio.create_task(asyncio.to_thread(request, descriptor))
                received = await owner.call_tool("next_game_question", {"wait_seconds": 2})
                self.assertFalse(received.is_error)
                request_id = received.structured_content["question"]["request_id"]
                unavailable = await other.call_tool("next_game_question", {"wait_seconds": 0})
                self.assertFalse(unavailable.is_error)
                self.assertIsNone(unavailable.structured_content.get("question"))
                hijack = await other.call_tool("reply_to_game", {"request_id": request_id, "reply": REPLY})
                self.assertTrue(hijack.is_error)
                self.assertEqual((await game)[0], 504)
                expired = await owner.call_tool("reply_to_game", {"request_id": request_id, "reply": REPLY})
                self.assertTrue(expired.is_error)

                retry_game = asyncio.create_task(asyncio.to_thread(request, descriptor))
                newer = await other.call_tool("next_game_question", {"wait_seconds": 2})
                newer_id = newer.structured_content["question"]["request_id"]
                self.assertNotEqual(newer_id, request_id)
                reply = await other.call_tool("reply_to_game", {"request_id": newer_id, "reply": REPLY})
                self.assertFalse(reply.is_error)
                self.assertEqual(await retry_game, (200, {"reply": REPLY}))

    async def test_authentication_and_mode_isolation(self):
        with isolated_relay(DesktopRelay(timeout=2)) as (_, descriptor):
            self.assertEqual((await asyncio.to_thread(request, descriptor, {}, token=False, path=DESKTOP_NEXT_PATH))[0], 401)
            self.assertEqual((await asyncio.to_thread(request, descriptor, {}, token="wrong", path=DESKTOP_NEXT_PATH))[0], 401)
        with model_fixture() as (model, calls), isolated_relay(model) as (game_dir, descriptor):
            async with stdio(game_dir) as client:
                outcome = await client.call_tool("next_game_question", {"wait_seconds": 0})
                self.assertTrue(outcome.is_error)
                self.assertIn("not in desktop MCP mode", str(outcome.content))
                self.assertEqual(await asyncio.to_thread(request, descriptor), (200, {"reply": REPLY}))
            self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
