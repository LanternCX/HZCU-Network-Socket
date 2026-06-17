"""TCP Echo Client — Task 1."""

import socket

import questionary
from loguru import logger
from rich.console import Console
from rich.panel import Panel

console = Console()
logger.remove()
logger.add(
    lambda msg: console.print(msg, end=""),
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
)

HOST = "127.0.0.1"
PORT = 9000
ENCODING = "utf-8"
BUFFER_SIZE = 4096


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
        logger.info(f"Connected to {HOST}:{PORT}")

        while True:
            message = questionary.text("You").ask()
            if not message or message.strip().lower() in ("quit", "exit"):
                break

            sock.sendall(message.encode(ENCODING))
            data = sock.recv(BUFFER_SIZE)
            response = data.decode(ENCODING)
            console.print(Panel(response, title="Server Echo", border_style="cyan"))
    except (ConnectionResetError, BrokenPipeError) as e:
        logger.error(f"Connection lost: {e}")
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        logger.info("Disconnected")


if __name__ == "__main__":
    main()
