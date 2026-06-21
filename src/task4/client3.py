"""Task 4 WebSocket browser client and TCP socket adapter."""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import re
import socket
import subprocess
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from loguru import logger
from rich.console import Console

console = Console()
logger.remove()
logger.add(
    lambda msg: console.print(msg, end=""),
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
)

WS_HOST = "127.0.0.1"
WS_PORT = 8765
RECEIVED_DIR = Path("data/task4/received")
UI_DIR = Path(__file__).resolve().parent / "ui"
UI_DIST_DIR = UI_DIR / "dist"

HOST = "127.0.0.1"
PORT = 9003
ENCODING = "utf-8"
BUFFER_SIZE = 4096
FILE_COMMAND = "/file"


@dataclass(frozen=True)
class FileTransfer:
    """Metadata for a task 4 file or image transfer."""

    filename: str
    size: int
    mime_type: str
    sender: str
    scope: str = "public"
    target: str = ""

    def to_header(self) -> str:
        payload = {
            "filename": self.filename,
            "size": self.size,
            "mime_type": self.mime_type,
            "sender": self.sender,
            "scope": self.scope,
            "target": self.target,
        }
        return f"{FILE_COMMAND} {json.dumps(payload, separators=(',', ':'))}\n"

    @classmethod
    def from_header(cls, header: str) -> "FileTransfer":
        command, payload = header.strip().split(maxsplit=1)
        if command != FILE_COMMAND:
            raise ValueError("Invalid file transfer command.")
        data = json.loads(payload)
        required = {"filename", "size", "mime_type", "sender", "scope", "target"}
        if set(data) != required:
            raise ValueError("Invalid file transfer metadata.")
        size = int(data["size"])
        if size < 0:
            raise ValueError("Invalid file size.")
        return cls(
            filename=str(data["filename"]),
            size=size,
            mime_type=str(data["mime_type"]),
            sender=str(data["sender"]),
            scope=str(data["scope"]),
            target=str(data["target"]),
        )


class SocketReader:
    """Buffered line and byte reader for mixed text/binary TCP payloads."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.buffer = b""

    def recv_line(self) -> str:
        while b"\n" not in self.buffer:
            chunk = self.sock.recv(BUFFER_SIZE)
            if not chunk:
                raise ConnectionError("Connection closed while reading line.")
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line.decode(ENCODING).strip()

    def recv_exact(self, size: int) -> bytes:
        while len(self.buffer) < size:
            chunk = self.sock.recv(BUFFER_SIZE)
            if not chunk:
                raise ConnectionError("Connection closed during file transfer.")
            self.buffer += chunk
        payload = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return payload


@dataclass(frozen=True)
class WebSocketBridgeEvent:
    type: str
    text: str = ""
    sender: str = ""
    users: list[str] | None = None
    rooms: list[str] | None = None
    room: str = ""
    participants: int | None = None
    creator: str = ""
    filename: str = ""
    mimeType: str = ""
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in ("", None)}


def translate_ui_event(event: dict[str, Any]) -> list[str]:
    event_type = event.get("type")
    if event_type == "command":
        text = str(event.get("text", "")).strip()
        return [text] if text else []
    if event_type == "message":
        text = str(event.get("text", "")).strip()
        if not text:
            return []
        if text.startswith("/"):
            return [text]
        return [f"/room {text}" if event.get("scope") == "room" else text]
    if event_type == "join_room":
        return [f"/join {event['room']}"]
    if event_type == "create_room":
        return [f"/create {event['room']}"]
    if event_type == "delete_room":
        return [f"/delete {event['room']}"]
    if event_type == "leave_room":
        return ["/leave"]
    if event_type == "private_message":
        return [f"/pm {event['target']} {event['text']}"]
    if event_type == "request_users":
        return ["/list"]
    if event_type == "request_help":
        return ["/help"]
    return []


def parse_server_message(message: str) -> WebSocketBridgeEvent:
    text = message.strip()
    private_match = re.match(r"^\[PM from ([^\]]+)]\s*(.*)$", text)
    if private_match:
        return WebSocketBridgeEvent(
            type="private_message",
            sender=private_match.group(1),
            text=private_match.group(2),
        )

    room_match = re.match(r"^\[ROOM ([^|]+) \| ([^\]]+)]\s*(.*)$", text)
    if room_match:
        return WebSocketBridgeEvent(
            type="room_message",
            room=room_match.group(1).strip(),
            sender=room_match.group(2).strip(),
            text=room_match.group(3),
        )

    users_match = re.match(r"^\[SERVER] Online users:\s*(.*)$", text)
    if users_match:
        users = [user.strip() for user in users_match.group(1).split(",") if user.strip()]
        return WebSocketBridgeEvent(type="users", users=users)

    rooms_match = re.match(r"^\[SERVER] Rooms:\s*(.*)$", text)
    if rooms_match:
        rooms = [room.strip() for room in rooms_match.group(1).split(",") if room.strip()]
        return WebSocketBridgeEvent(type="rooms", rooms=rooms)

    file_match = re.match(r"^\[FILE from ([^\]]+)]\s*(.*)$", text)
    if file_match:
        return WebSocketBridgeEvent(type="system", sender=file_match.group(1), text=file_match.group(2))

    if text.startswith("[SERVER]"):
        return WebSocketBridgeEvent(type="system", text=text.removeprefix("[SERVER]").strip())

    chat_match = re.match(r"^\[([^\]]+)]\s*(.*)$", text)
    if chat_match:
        return WebSocketBridgeEvent(
            type="message",
            sender=chat_match.group(1),
            text=chat_match.group(2),
        )

    return WebSocketBridgeEvent(type="message", text=text)


def safe_filename(filename: str) -> str:
    candidate = Path(filename).name.strip() or "received-file"
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", candidate)
    return cleaned or "received-file"


def save_received_file(
    directory: Path,
    filename: str,
    payload: bytes,
    mime_type: str,
    sender: str,
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    clean_name = safe_filename(filename)
    target = directory / clean_name
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        target = directory / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
    target.write_bytes(payload)
    return {
        "type": "file_received",
        "filename": clean_name,
        "mimeType": mime_type,
        "path": f"/received/{quote(target.name)}",
        "size": len(payload),
        "sender": sender,
    }


def decode_ui_file_payload(payload: str) -> bytes:
    return base64.b64decode(payload.encode(ENCODING), validate=True)


def build_file_transfer(
    filename: str,
    payload: bytes,
    sender: str,
    scope: str = "public",
    target: str = "",
    mime_type: str | None = None,
) -> tuple[str, bytes]:
    guessed_type = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    transfer = FileTransfer(
        filename=safe_filename(filename),
        size=len(payload),
        mime_type=guessed_type,
        sender=sender,
        scope=scope,
        target=target,
    )
    return transfer.to_header(), payload


class TcpChatAdapter:
    """TCP socket side of the task 4 client bridge."""

    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None
        self.reader: TcpEventReader | None = None

    def connect(self, username: str) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.sock.recv(BUFFER_SIZE)
        self.sock.sendall(f"{username}\n".encode(ENCODING))
        self.reader = TcpEventReader(self.sock, RECEIVED_DIR)

    def send_text(self, text: str) -> None:
        if self.sock is None:
            raise ConnectionError("TCP socket is not connected.")
        self.sock.sendall(f"{text}\n".encode(ENCODING))

    def send_file(self, header: str, payload: bytes) -> None:
        if self.sock is None:
            raise ConnectionError("TCP socket is not connected.")
        self.sock.sendall(header.encode(ENCODING))
        self.sock.sendall(payload)

    def receive_event(self) -> dict[str, Any]:
        if self.reader is None:
            raise ConnectionError("TCP socket is not connected.")
        return self.reader.next_event()

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None
            self.reader = None


class TcpEventReader:
    """Converts framed TCP server output into WebSocket-friendly events."""

    def __init__(self, sock: socket.socket, receive_dir: Path = RECEIVED_DIR) -> None:
        self.reader = SocketReader(sock)
        self.receive_dir = receive_dir

    def next_event(self) -> dict[str, Any]:
        line = self.reader.recv_line()
        if line.startswith(f"{FILE_COMMAND} "):
            transfer = FileTransfer.from_header(line)
            payload = self.reader.recv_exact(transfer.size)
            return save_received_file(
                directory=self.receive_dir,
                filename=transfer.filename,
                payload=payload,
                mime_type=transfer.mime_type,
                sender=transfer.sender,
            )
        return parse_server_message(line).to_dict()


async def handle_websocket(websocket: Any) -> None:
    adapter: TcpChatAdapter | None = None
    receive_task: asyncio.Task[None] | None = None

    async def forward_tcp_to_ws() -> None:
        if adapter is None:
            return
        while True:
            try:
                event = await asyncio.to_thread(adapter.receive_event)
            except ConnectionError:
                await websocket.send(json.dumps({"type": "disconnected", "text": "TCP server disconnected."}))
                break
            await websocket.send(json.dumps(event))

    try:
        async for raw_message in websocket:
            event = json.loads(raw_message)
            if event.get("type") == "connect":
                username = str(event.get("username") or "web-user")
                host = str(event.get("host") or HOST)
                port = int(event.get("port") or PORT)
                adapter = TcpChatAdapter(host, port)
                await asyncio.to_thread(adapter.connect, username)
                receive_task = asyncio.create_task(forward_tcp_to_ws())
                await websocket.send(json.dumps({"type": "connected", "username": username}))
                continue

            if adapter is None:
                await websocket.send(json.dumps({"type": "error", "text": "Connect before sending messages."}))
                continue

            if event.get("type") == "send_file":
                filename = str(event.get("filename") or "file")
                payload = decode_ui_file_payload(str(event.get("payload") or ""))
                header, data = build_file_transfer(
                    filename=filename,
                    payload=payload,
                    sender=str(event.get("sender") or "web-user"),
                    scope=str(event.get("scope") or "public"),
                    target=str(event.get("target") or ""),
                    mime_type=event.get("mimeType"),
                )
                await asyncio.to_thread(adapter.send_file, header, data)
                continue

            for command in translate_ui_event(event):
                await asyncio.to_thread(adapter.send_text, command)
    finally:
        if receive_task is not None:
            receive_task.cancel()
        if adapter is not None:
            adapter.close()


async def run_websocket_server(host: str = WS_HOST, port: int = WS_PORT) -> None:
    import websockets

    port = choose_web_port(host) if port == WS_PORT else port
    ensure_ui_dist()
    async with websockets.serve(
        handle_websocket,
        host,
        port,
        process_request=serve_web_or_accept_websocket,
        max_size=None,
    ):
        logger.info(f"Task 4 client hosting web UI and WebSocket bridge on http://{host}:{port}")
        await asyncio.Future()


def ensure_ui_dist() -> None:
    if (UI_DIST_DIR / "index.html").exists():
        return
    subprocess.run(["npm", "run", "build"], cwd=UI_DIR, check=True)


def choose_web_port(host: str = WS_HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def serve_web_or_accept_websocket(_connection: Any, request: Any) -> Any:
    upgrade = request.headers.get("Upgrade", "")
    if upgrade.lower() == "websocket":
        return None

    from websockets.datastructures import Headers
    from websockets.http11 import Response

    try:
        ensure_ui_dist()
        file_path = resolve_web_path(getattr(request, "path", "/"))
        if not file_path.exists() or not file_path.is_file():
            file_path = UI_DIST_DIR / "index.html"
        body = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        return Response(
            200,
            "OK",
            Headers(
                [
                    ("Content-Type", content_type),
                    ("Content-Length", str(len(body))),
                ]
            ),
            body,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        body = f"Task 4 web UI is not available: {exc}\n".encode(ENCODING)
        return Response(
            503,
            "Service Unavailable",
            Headers(
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("Content-Length", str(len(body))),
                ]
            ),
            body,
        )


def resolve_web_path(request_path: str) -> Path:
    clean_path = unquote(request_path.split("?", 1)[0]).lstrip("/")
    if clean_path.startswith("received/"):
        candidate = (RECEIVED_DIR / clean_path.removeprefix("received/")).resolve()
        received_root = RECEIVED_DIR.resolve()
        if received_root not in candidate.parents and candidate != received_root:
            return UI_DIST_DIR / "index.html"
        return candidate
    if clean_path in ("", "/"):
        clean_path = "index.html"
    candidate = (UI_DIST_DIR / clean_path).resolve()
    dist_root = UI_DIST_DIR.resolve()
    if dist_root not in candidate.parents and candidate != dist_root:
        return UI_DIST_DIR / "index.html"
    return candidate


def main() -> None:
    asyncio.run(run_websocket_server())


if __name__ == "__main__":
    main()
