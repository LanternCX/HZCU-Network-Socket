import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from websockets.datastructures import Headers

from src.task4.client3 import (
    FileTransfer,
    TcpEventReader,
    WebSocketBridgeEvent,
    decode_ui_file_payload,
    parse_server_message,
    run_websocket_server,
    serve_web_or_accept_websocket,
    save_received_file,
    translate_ui_event,
)


class ChunkedSocket:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    def recv(self, size: int) -> bytes:
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if len(chunk) <= size:
            return chunk
        self.chunks.insert(0, chunk[size:])
        return chunk[:size]


class StopServer(Exception):
    pass


class StopFuture:
    def __await__(self):
        raise StopServer
        yield


class FakeServe:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class Task4ClientBridgeTest(unittest.TestCase):
    def test_translates_ui_actions_to_tcp_commands(self) -> None:
        cases = [
            ({"type": "join_room", "room": "general"}, ["/join general"]),
            ({"type": "create_room", "room": "study"}, ["/create study"]),
            ({"type": "delete_room", "room": "study"}, ["/delete study"]),
            ({"type": "leave_room"}, ["/leave"]),
            ({"type": "private_message", "target": "bob", "text": "hello"}, ["/pm bob hello"]),
            ({"type": "message", "scope": "room", "text": "hi room"}, ["/room hi room"]),
            ({"type": "request_users"}, ["/list"]),
            ({"type": "request_help"}, ["/help"]),
        ]

        for event, expected in cases:
            with self.subTest(event=event):
                self.assertEqual(translate_ui_event(event), expected)

    def test_slash_commands_pass_through_unchanged(self) -> None:
        self.assertEqual(
            translate_ui_event({"type": "command", "text": "/join project"}),
            ["/join project"],
        )

    def test_received_file_is_stored_with_safe_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            event = save_received_file(
                directory=Path(tmpdir),
                filename="../notes.txt",
                payload=b"saved content",
                mime_type="text/plain",
                sender="alice",
            )

            saved_path = Path(tmpdir) / "notes.txt"
            self.assertEqual(saved_path.parent, Path(tmpdir))
            self.assertEqual(saved_path.read_bytes(), b"saved content")
            self.assertEqual(event["type"], "file_received")
            self.assertEqual(event["filename"], "notes.txt")
            self.assertEqual(event["path"], "/received/notes.txt")

    def test_received_files_are_served_to_browser(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "notes.txt").write_bytes(b"saved content")
            request = SimpleNamespace(
                path="/received/notes.txt",
                headers=Headers([("Connection", "keep-alive")]),
            )

            with patch("src.task4.client3.RECEIVED_DIR", Path(tmpdir)):
                response = serve_web_or_accept_websocket(None, request)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.body, b"saved content")
            self.assertEqual(response.headers["Content-Type"], "text/plain")

    def test_decodes_base64_file_payload_from_ui(self) -> None:
        self.assertEqual(decode_ui_file_payload("c2F2ZWQgY29udGVudA=="), b"saved content")

    def test_tcp_event_reader_stores_received_file_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = b"saved content"
            transfer = FileTransfer(
                filename="notes.txt",
                size=len(payload),
                mime_type="text/plain",
                sender="alice",
                scope="public",
                target="",
            )
            reader = TcpEventReader(
                sock=ChunkedSocket([transfer.to_header().encode("utf-8") + payload]),
                receive_dir=Path(tmpdir),
            )

            event = reader.next_event()

            self.assertEqual(event["type"], "file_received")
            self.assertEqual(Path(tmpdir, "notes.txt").read_bytes(), payload)
            self.assertEqual(event["path"], "/received/notes.txt")

    def test_server_messages_become_ui_events(self) -> None:
        self.assertEqual(
            parse_server_message("[PM from bob] hello"),
            WebSocketBridgeEvent(type="private_message", sender="bob", text="hello"),
        )
        self.assertEqual(
            parse_server_message("[SERVER] Online users: alice, bob"),
            WebSocketBridgeEvent(type="users", users=["alice", "bob"]),
        )

    def test_plain_http_request_to_client_port_serves_react_index(self) -> None:
        request = SimpleNamespace(path="/", headers=Headers([("Connection", "keep-alive")]))

        response = serve_web_or_accept_websocket(None, request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', response.body)

    def test_websocket_upgrade_request_is_accepted_by_bridge(self) -> None:
        request = SimpleNamespace(path="/", headers=Headers([("Upgrade", "websocket")]))

        self.assertIsNone(serve_web_or_accept_websocket(None, request))

    def test_choose_web_port_finds_a_free_port(self) -> None:
        from src.task4.client3 import choose_web_port

        port = choose_web_port()

        self.assertIsInstance(port, int)
        self.assertGreater(port, 0)

    def test_websocket_server_allows_large_file_messages(self) -> None:
        serve_call: dict[str, object] = {}

        def fake_serve(*_args: object, **kwargs: object) -> FakeServe:
            serve_call.update(kwargs)
            return FakeServe()

        with (
            patch("websockets.serve", fake_serve),
            patch("src.task4.client3.ensure_ui_dist"),
            patch("src.task4.client3.asyncio.Future", return_value=StopFuture()),
        ):
            with self.assertRaises(StopServer):
                asyncio.run(run_websocket_server(port=9999))

        self.assertIsNone(serve_call["max_size"])


if __name__ == "__main__":
    unittest.main()
