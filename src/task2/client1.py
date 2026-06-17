"""Multi-person Chat Room Client — Task 2."""

import socket
import threading

import questionary
from loguru import logger
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

console = Console()
logger.remove()
logger.add(
    lambda msg: console.print(msg, end=""),
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
)

HOST = "127.0.0.1"
PORT = 9001
ENCODING = "utf-8"
BUFFER_SIZE = 4096


def receive_messages(sock: socket.socket) -> None:
    """Continuously receive and display messages from the server."""
    while True:
        try:
            data = sock.recv(BUFFER_SIZE)
            if not data:
                break
            message = data.decode(ENCODING)
            logger.info(message.strip())
        except (ConnectionResetError, OSError):
            break
    logger.info("Disconnected from server.")


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
        logger.info(f"Connected to {HOST}:{PORT}")
    except ConnectionRefusedError:
        logger.error("Cannot connect to the server. Is it running?")
        return

    try:
        with patch_stdout(raw=True):
            # Wait for the server username prompt, then ask locally.
            sock.recv(BUFFER_SIZE)
            username = questionary.text("Username").ask()
            if not username:
                username = ""
            sock.sendall(username.encode(ENCODING))

            # Start receiving messages in background
            recv_thread = threading.Thread(target=receive_messages, args=(sock,), daemon=True)
            recv_thread.start()

            # Main loop: read input and send messages
            while True:
                message = questionary.text("You").ask()
                if not message or message.strip().lower() in ("quit", "exit"):
                    break
                sock.sendall(message.encode(ENCODING))
    except (ConnectionResetError, BrokenPipeError) as e:
        logger.error(f"Connection lost: {e}")
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        logger.info("Disconnected")


if __name__ == "__main__":
    main()
