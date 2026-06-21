"""Graphical Chat Tool TCP Server — Task 4."""

from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass

from loguru import logger
from rich.console import Console

console = Console()
logger.remove()
logger.add(
    lambda msg: console.print(msg, end=""),
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
)

HOST = "0.0.0.0"
PORT = 9003
ENCODING = "utf-8"
BUFFER_SIZE = 4096
FILE_COMMAND = "/file"
DEFAULT_ROOM = "general"


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


class ChatServerState:
    """Thread-safe state and command handling for the task 4 chat server."""

    def __init__(self) -> None:
        self.clients: dict[socket.socket, str] = {}
        self.rooms: dict[str, set[socket.socket]] = {}
        self.client_rooms: dict[socket.socket, str | None] = {}
        self.lock = threading.RLock()

    def add_client(self, client_sock: socket.socket, username: str) -> None:
        with self.lock:
            self.clients[client_sock] = username
            self.rooms.setdefault(DEFAULT_ROOM, set()).add(client_sock)
            self.client_rooms[client_sock] = DEFAULT_ROOM
        self.broadcast_online_users()

    def remove_client(self, client_sock: socket.socket) -> str:
        with self.lock:
            username = self.clients.pop(client_sock, "Unknown")
            room_name = self.client_rooms.pop(client_sock, None)
            if room_name and room_name in self.rooms:
                self.rooms[room_name].discard(client_sock)
        self.broadcast_online_users()
        return username

    def send_to(self, client_sock: socket.socket, message: str | bytes) -> None:
        data = message if isinstance(message, bytes) else message.encode(ENCODING)
        try:
            client_sock.sendall(data)
        except OSError:
            pass

    def broadcast(self, message: str, sender: socket.socket | None = None) -> None:
        with self.lock:
            recipients = [client_sock for client_sock in self.clients if client_sock is not sender]
        for client_sock in recipients:
            self.send_to(client_sock, message)

    def online_users_message(self) -> str:
        with self.lock:
            users = ", ".join(sorted(self.clients.values()))
        return f"[SERVER] Online users: {users}\n"

    def broadcast_online_users(self) -> None:
        message = self.online_users_message()
        with self.lock:
            recipients = list(self.clients)
        for client_sock in recipients:
            self.send_to(client_sock, message)

    def rooms_message(self) -> str:
        with self.lock:
            room_names = sorted(self.rooms)
        return f"[SERVER] Rooms: {', '.join(room_names)}\n"

    def broadcast_rooms(self) -> None:
        message = self.rooms_message()
        with self.lock:
            recipients = list(self.clients)
        for client_sock in recipients:
            self.send_to(client_sock, message)

    def room_broadcast(self, room_name: str, message: str, sender: socket.socket) -> None:
        with self.lock:
            members = list(self.rooms.get(room_name, set()))
        for member in members:
            if member is not sender:
                self.send_to(member, message)

    def leave_current_room_locked(self, client_sock: socket.socket) -> str | None:
        room_name = self.client_rooms.get(client_sock)
        if room_name and room_name in self.rooms:
            self.rooms[room_name].discard(client_sock)
        self.client_rooms[client_sock] = None
        return room_name

    def handle_chat_message(self, sender: socket.socket, message: str) -> None:
        with self.lock:
            username = self.clients.get(sender, "Unknown")
        logger.info(f"[{username}] {message}")
        self.broadcast(f"[{username}] {message}\n", sender=sender)

    def handle_command(self, sender: socket.socket, message: str) -> None:
        if message.startswith(f"{FILE_COMMAND} "):
            self.send_to(sender, "[SERVER] Send file metadata followed by binary payload.\n")
            return

        parts = message.split(maxsplit=2)
        command = parts[0].lower()

        if command == "/help":
            self._handle_help(sender)
        elif command == "/list":
            self._handle_list(sender)
        elif command == "/pm":
            self._handle_private_message(sender, parts)
        elif command == "/create":
            self._handle_create_room(sender, parts)
        elif command == "/delete":
            self._handle_delete_room(sender, parts)
        elif command == "/join":
            self._handle_join_room(sender, parts)
        elif command == "/leave":
            self._handle_leave_room(sender)
        elif command == "/room":
            self._handle_room_message(sender, message)
        else:
            self.send_to(sender, "[SERVER] Unknown command. Type /help for help.\n")

    def route_file_transfer(
        self,
        sender: socket.socket,
        transfer: FileTransfer,
        payload: bytes,
    ) -> None:
        if transfer.size != len(payload):
            self.send_to(sender, "[SERVER] File transfer failed: size mismatch.\n")
            return

        recipients = self._file_recipients(sender, transfer)
        if not recipients:
            self.send_to(sender, "[SERVER] File transfer failed: no recipients.\n")
            return

        notice = (
            f"[FILE from {transfer.sender}] {transfer.filename} "
            f"({transfer.size} bytes, {transfer.mime_type})\n"
        )
        header = transfer.to_header().encode(ENCODING)
        for recipient in recipients:
            self.send_to(recipient, notice)
            self.send_to(recipient, header)
            self.send_to(recipient, payload)
        self.send_to(sender, f"[SERVER] Sent file: {transfer.filename}\n")

    def _file_recipients(self, sender: socket.socket, transfer: FileTransfer) -> list[socket.socket]:
        with self.lock:
            if transfer.scope == "room":
                return [
                    client_sock
                    for client_sock in self.rooms.get(transfer.target, set())
                    if client_sock is not sender
                ]
            if transfer.scope == "private":
                return [
                    client_sock
                    for client_sock, username in self.clients.items()
                    if username == transfer.target and client_sock is not sender
                ]
            return [client_sock for client_sock in self.clients if client_sock is not sender]

    def _handle_help(self, sender: socket.socket) -> None:
        help_text = (
            "[SERVER] Commands:\n"
            "  /pm <user> <message> - send a private message\n"
            "  /create <room> - create and enter a room\n"
            "  /delete <room> - delete a room\n"
            "  /join <room> - join a room\n"
            "  /leave - leave the current room\n"
            "  /room <message> - send a message to the current room\n"
            "  /file <metadata> - send file metadata followed by file bytes\n"
            "  /list - list online users\n"
            "  /help - show this help\n"
        )
        self.send_to(sender, help_text)

    def _handle_list(self, sender: socket.socket) -> None:
        self.send_to(sender, self.online_users_message())

    def _handle_private_message(self, sender: socket.socket, parts: list[str]) -> None:
        if len(parts) < 3:
            self.send_to(sender, "[SERVER] Usage: /pm <user> <message>\n")
            return

        target_name = parts[1]
        text = parts[2]
        with self.lock:
            sender_name = self.clients.get(sender, "Unknown")
            target_sock = next(
                (client_sock for client_sock, username in self.clients.items() if username == target_name),
                None,
            )

        if target_sock is None:
            self.send_to(sender, f"[SERVER] User not found: {target_name}\n")
            return

        self.send_to(target_sock, f"[PM from {sender_name}] {text}\n")
        self.send_to(sender, f"[PM to {target_name}] {text}\n")

    def _handle_create_room(self, sender: socket.socket, parts: list[str]) -> None:
        if len(parts) < 2:
            self.send_to(sender, "[SERVER] Usage: /create <room>\n")
            return

        room_name = parts[1]
        with self.lock:
            if room_name in self.rooms:
                self.send_to(sender, f"[SERVER] Room already exists: {room_name}\n")
                return
            self.leave_current_room_locked(sender)
            self.rooms[room_name] = {sender}
            self.client_rooms[sender] = room_name
        self.broadcast_rooms()
        self.send_to(sender, f"[SERVER] Created and joined room: {room_name}\n")

    def _handle_delete_room(self, sender: socket.socket, parts: list[str]) -> None:
        if len(parts) < 2:
            self.send_to(sender, "[SERVER] Usage: /delete <room>\n")
            return

        room_name = parts[1]
        if room_name == DEFAULT_ROOM:
            self.send_to(sender, "[SERVER] The general room cannot be deleted.\n")
            return

        with self.lock:
            if room_name not in self.rooms:
                self.send_to(sender, f"[SERVER] Room not found: {room_name}\n")
                return
            members = list(self.rooms.pop(room_name))
            self.rooms.setdefault(DEFAULT_ROOM, set()).update(members)
            for member in members:
                self.client_rooms[member] = DEFAULT_ROOM
        self.broadcast_rooms()
        self.send_to(sender, f"[SERVER] Deleted room: {room_name}\n")

    def _handle_join_room(self, sender: socket.socket, parts: list[str]) -> None:
        if len(parts) < 2:
            self.send_to(sender, "[SERVER] Usage: /join <room>\n")
            return

        room_name = parts[1]
        with self.lock:
            if room_name not in self.rooms:
                self.send_to(sender, f"[SERVER] Room not found: {room_name}\n")
                return
            if self.client_rooms.get(sender) == room_name:
                self.send_to(sender, f"[SERVER] You are already in room: {room_name}\n")
                return
            self.leave_current_room_locked(sender)
            self.rooms[room_name].add(sender)
            self.client_rooms[sender] = room_name
            username = self.clients.get(sender, "Unknown")
        self.broadcast_rooms()
        self.send_to(sender, f"[SERVER] Joined room: {room_name}\n")
        self.room_broadcast(room_name, f"[SERVER] {username} joined room {room_name}.\n", sender)

    def _handle_leave_room(self, sender: socket.socket) -> None:
        with self.lock:
            room_name = self.client_rooms.get(sender)
            username = self.clients.get(sender, "Unknown")
            if not room_name:
                self.send_to(sender, "[SERVER] You are not in a room.\n")
                return
            self.leave_current_room_locked(sender)
        self.broadcast_rooms()
        self.send_to(sender, f"[SERVER] Left room: {room_name}\n")
        self.room_broadcast(room_name, f"[SERVER] {username} left room {room_name}.\n", sender)

    def _handle_room_message(self, sender: socket.socket, message: str) -> None:
        command_parts = message.split(maxsplit=1)
        if len(command_parts) < 2:
            self.send_to(sender, "[SERVER] Usage: /room <message>\n")
            return

        text = command_parts[1]
        with self.lock:
            room_name = self.client_rooms.get(sender)
            username = self.clients.get(sender, "Unknown")
        if not room_name:
            self.send_to(sender, "[SERVER] Join a room before sending room messages.\n")
            return

        logger.info(f"[ROOM {room_name} | {username}] {text}")
        self.room_broadcast(room_name, f"[ROOM {room_name} | {username}] {text}\n", sender)


state = ChatServerState()


def handle_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    """Handle a single task 4 TCP client connection."""
    logger.info(f"Client connected: {addr[0]}:{addr[1]}")
    try:
        conn.sendall("Enter your username: ".encode(ENCODING))
        reader = SocketReader(conn)
        username = reader.recv_line() or f"User-{addr[1]}"

        state.add_client(conn, username)
        state.broadcast(f"[SERVER] {username} has joined the chat.\n", sender=conn)
        conn.sendall(f"[SERVER] Welcome, {username}! Type /help for commands.\n".encode(ENCODING))

        while True:
            message = reader.recv_line()
            if not message:
                continue
            if message.startswith(f"{FILE_COMMAND} "):
                transfer = FileTransfer.from_header(message)
                payload = reader.recv_exact(transfer.size)
                state.route_file_transfer(conn, transfer, payload)
            elif message.startswith("/"):
                state.handle_command(conn, message)
            else:
                state.handle_chat_message(conn, message)
    except (ConnectionResetError, ConnectionError, OSError, UnicodeDecodeError, ValueError):
        pass
    finally:
        username = state.remove_client(conn)
        conn.close()
        leave_msg = f"[SERVER] {username} has left the chat.\n"
        logger.info(leave_msg.strip())
        state.broadcast(leave_msg)


def main() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    logger.info(f"Task 4 TCP chat server listening on {HOST}:{PORT}")

    try:
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    finally:
        with state.lock:
            client_socks = list(state.clients)
            state.clients.clear()
            state.rooms.clear()
            state.client_rooms.clear()
        for client_sock in client_socks:
            try:
                client_sock.sendall("[SERVER] Server is shutting down.\n".encode(ENCODING))
                client_sock.close()
            except OSError:
                pass
        server.close()


if __name__ == "__main__":
    main()
