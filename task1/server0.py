"""TCP Echo Server — Task 1."""

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
PORT = 9000
ENCODING = "utf-8"
BUFFER_SIZE = 4096


def handle_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    logger.info(f"Client connected: {addr[0]}:{addr[1]}")
    try:
        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                break
            message = data.decode(ENCODING)
            logger.info(f"[{addr[0]}:{addr[1]}] -> {message!r}")
            conn.sendall(data)
            logger.info(f"[{addr[0]}:{addr[1]}] <- echo: {message!r}")
    except (ConnectionResetError, OSError):
        pass
    finally:
        conn.close()
        logger.info(f"Client disconnected: {addr[0]}:{addr[1]}")


def main() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    logger.info(f"Server listening on {HOST}:{PORT}")

    try:
        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    main()
