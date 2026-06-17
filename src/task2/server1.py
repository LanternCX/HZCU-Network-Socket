"""Multi-person Chat Room Server — Task 2."""

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
PORT = 9001
ENCODING = "utf-8"
BUFFER_SIZE = 4096

clients: dict[socket.socket, str] = {}
clients_lock = threading.Lock()


def broadcast(message: str, sender: socket.socket | None = None) -> None:
    """Send a message to all connected clients except the sender."""
    with clients_lock:
        for client_sock in list(clients):
            if client_sock is not sender:
                try:
                    client_sock.sendall(message.encode(ENCODING))
                except OSError:
                    pass


def handle_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    """Handle a single client connection."""
    logger.info(f"Client connected: {addr[0]}:{addr[1]}")
    try:
        # Ask for username
        conn.sendall("Enter your username: ".encode(ENCODING))
        username_data = conn.recv(BUFFER_SIZE)
        if not username_data:
            conn.close()
            return
        username = username_data.decode(ENCODING).strip()
        if not username:
            username = f"User-{addr[1]}"

        with clients_lock:
            clients[conn] = username

        join_msg = f"[SERVER] {username} has joined the chat."
        logger.info(join_msg)
        broadcast(join_msg, sender=conn)
        conn.sendall(f"[SERVER] Welcome, {username}!\n".encode(ENCODING))

        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                break
            message = data.decode(ENCODING).strip()
            if not message:
                continue
            logger.info(f"[{username}] {message}")
            broadcast(f"[{username}] {message}", sender=conn)
    except (ConnectionResetError, OSError):
        pass
    finally:
        with clients_lock:
            username = clients.pop(conn, "Unknown")
        conn.close()
        leave_msg = f"[SERVER] {username} has left the chat."
        logger.info(leave_msg)
        broadcast(leave_msg)


def main() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    logger.info(f"Chat server listening on {HOST}:{PORT}")

    try:
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    finally:
        with clients_lock:
            for client_sock in clients:
                try:
                    client_sock.sendall("[SERVER] Server is shutting down.\n".encode(ENCODING))
                    client_sock.close()
                except OSError:
                    pass
            clients.clear()
        server.close()


if __name__ == "__main__":
    main()
