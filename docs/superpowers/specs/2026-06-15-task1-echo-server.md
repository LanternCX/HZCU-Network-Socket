# Task 1: Basic TCP Communication (Echo Server) — Spec

**Status:** Draft  
**Date:** 2026-06-15

---

## Objective

Implement a basic TCP echo server (`server0`) and client (`client0`) in Python. Demonstrate the full socket lifecycle: create, bind, listen, connect, send, receive, close. Use multi-threading on the server to handle concurrent clients.

## Architecture

Two standalone Python scripts, organized under `task1/`:

- `server0.py` — TCP server that echoes received messages back to the sender
- `client0.py` — interactive TCP client with rich CLI

Communication flow:

```
[Terminal 1: server0.py]  ←── TCP socket ──→  [Terminal 2: client0.py]
```

No HTTP layer, no frontend. Pure socket-to-socket communication.

## Tech Stack

| Component | Tool |
| --- | --- |
| Language | Python 3.12+ |
| Package manager | uv |
| CLI interaction | questionary |
| Terminal output | rich |
| Logging | loguru (with rich sink) |
| Socket | Python stdlib `socket`, `threading` |

## Project Structure

```
HZCU-Network-Socket/
├── pyproject.toml          # uv-managed dependencies
├── README.md               # project docs
├── task1/
│   ├── server0.py          # TCP echo server
│   └── client0.py          # TCP echo client
└── docs/
    └── superpowers/
        ├── specs/          # this file
        └── plans/          # implementation plan
```

## Detailed Design

### Shared defaults (inline in each script)

- Host: `0.0.0.0` (server) / `127.0.0.1` (client)
- Port: `9000`
- Encoding: `utf-8`
- Buffer size: `4096` bytes

### task1/server0.py

**Startup:**
- Create a TCP socket (`socket.AF_INET`, `socket.SOCK_STREAM`)
- Set `SO_REUSEADDR` to avoid "address already in use" on restart
- Bind to `(host, port)`
- Listen with a backlog of 5
- Log startup info via loguru with rich formatting (host, port, waiting state)

**Connection loop:**
- Accept connections in a loop
- For each connection, log client address (IP, port)
- Spawn a daemon thread running `handle_client(conn, addr)`

**handle_client(conn, addr):**
- Loop: receive data from client
- If data is empty → client disconnected, log and close
- Otherwise: log received message, echo it back via `conn.sendall()`
- Catch `ConnectionResetError` / `OSError` for abrupt disconnects
- On exit: log disconnection, close socket

**Shutdown:**
- Ctrl+C triggers graceful shutdown
- Log shutdown message, close server socket

### task1/client0.py

**Startup:**
- Create TCP socket
- Connect to `(host, port)`
- Log connection success via loguru + rich

**Interactive loop:**
- Use `questionary.text()` for user input
- If input is empty or `quit`/`exit` → break
- Send input to server via `socket.sendall()`
- Receive response from server
- Display response using `rich.panel.Panel` with "Server Echo" title
- Handle `ConnectionResetError` / `BrokenPipeError` → log error, exit loop

**Shutdown:**
- Close socket on exit
- Log disconnection

### Logging style

- Use loguru's default logger with `rich` sink (via `rich.console.Console`)
- Server: log each connection event (connect/disconnect) and each message (direction + content)
- Client: log connection status and errors
- Keep log format clean: timestamp, level, message

## Out of Scope

- React frontend (Task 4)
- Chat rooms, private messaging, file transfer (Task 2+)
- Wireshark capture (manual step, referenced in README)
- Unit tests (Task 1 is exploratory / demo; behavior tests introduced with Task 2)

## Acceptance Criteria

1. `uv run task1/server0.py` starts the server, logs listening address
2. `uv run task1/client0.py` connects, shows interactive prompt
3. Typing a message in client → server echoes it back → client displays in a rich panel
4. Multiple clients can connect simultaneously (each in a separate terminal)
5. Disconnecting a client (Ctrl+C or `quit`) does not crash the server
6. Ctrl+C on server exits cleanly with a log message
