"""Enhanced Chat Room Server — Task 3."""

import socket
import threading

from loguru import logger
from rich.console import Console

console = Console()
logger.remove()
logger.add(
    lambda msg: console.print(msg, end=""),
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
)

HOST = "0.0.0.0"
PORT = 9002
ENCODING = "utf-8"
BUFFER_SIZE = 4096


class ChatServerState:
    """Thread-safe state and command handling for the task 3 chat server."""

    def __init__(self) -> None:
        self.clients: dict[socket.socket, str] = {}
        self.rooms: dict[str, set[socket.socket]] = {}
        self.client_rooms: dict[socket.socket, str | None] = {}
        self.lock = threading.RLock()

    def add_client(self, client_sock: socket.socket, username: str) -> None:
        with self.lock:
            self.clients[client_sock] = username
            self.client_rooms[client_sock] = None

    def remove_client(self, client_sock: socket.socket) -> str:
        with self.lock:
            username = self.clients.pop(client_sock, "Unknown")
            room_name = self.client_rooms.pop(client_sock, None)
            if room_name and room_name in self.rooms:
                self.rooms[room_name].discard(client_sock)
                if not self.rooms[room_name]:
                    del self.rooms[room_name]
            return username

    def send_to(self, client_sock: socket.socket, message: str) -> None:
        try:
            client_sock.sendall(message.encode(ENCODING))
        except OSError:
            pass

    def broadcast(self, message: str, sender: socket.socket | None = None) -> None:
        with self.lock:
            recipients = [client_sock for client_sock in self.clients if client_sock is not sender]
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
            if not self.rooms[room_name]:
                del self.rooms[room_name]
        self.client_rooms[client_sock] = None
        return room_name

    def handle_chat_message(self, sender: socket.socket, message: str) -> None:
        with self.lock:
            username = self.clients.get(sender, "Unknown")
        logger.info(f"[{username}] {message}")
        self.broadcast(f"[{username}] {message}\n", sender=sender)

    def handle_command(self, sender: socket.socket, message: str) -> None:
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
        elif command == "/join":
            self._handle_join_room(sender, parts)
        elif command == "/leave":
            self._handle_leave_room(sender)
        elif command == "/room":
            self._handle_room_message(sender, message)
        else:
            self.send_to(sender, "[SERVER] Unknown command. Type /help for help.\n")

    def _handle_help(self, sender: socket.socket) -> None:
        help_text = (
            "[SERVER] Commands:\n"
            "  /pm <user> <message> - send a private message\n"
            "  /create <room> - create and enter a room\n"
            "  /join <room> - join a room\n"
            "  /leave - leave the current room\n"
            "  /room <message> - send a message to the current room\n"
            "  /list - list online users\n"
            "  /help - show this help\n"
        )
        self.send_to(sender, help_text)

    def _handle_list(self, sender: socket.socket) -> None:
        with self.lock:
            users = ", ".join(sorted(self.clients.values()))
        self.send_to(sender, f"[SERVER] Online users: {users}\n")

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
        self.send_to(sender, f"[SERVER] Created and joined room: {room_name}\n")

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
    """Handle a single client connection."""
    logger.info(f"Client connected: {addr[0]}:{addr[1]}")
    try:
        conn.sendall("Enter your username: ".encode(ENCODING))
        username_data = conn.recv(BUFFER_SIZE)
        if not username_data:
            conn.close()
            return
        username = username_data.decode(ENCODING).strip() or f"User-{addr[1]}"

        state.add_client(conn, username)
        state.broadcast(f"[SERVER] {username} has joined the chat.\n", sender=conn)
        conn.sendall(f"[SERVER] Welcome, {username}! Type /help for commands.\n".encode(ENCODING))

        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                break
            message = data.decode(ENCODING).strip()
            if not message:
                continue
            if message.startswith("/"):
                state.handle_command(conn, message)
            else:
                state.handle_chat_message(conn, message)
    except (ConnectionResetError, OSError):
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
    logger.info(f"Enhanced chat server listening on {HOST}:{PORT}")

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
