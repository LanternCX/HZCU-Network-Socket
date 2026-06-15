# Task 1: Basic TCP Communication (Echo Server) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a TCP echo server and client in Python with rich CLI, demonstrating the full socket lifecycle.

**Architecture:** Two standalone Python scripts under `task1/` — a multi-threaded TCP echo server and an interactive client. No shared config file; defaults are defined inline in each script.

**Tech Stack:** Python 3.12+, uv, loguru, rich, questionary, stdlib socket/threading

---

## File Structure

```
HZCU-Network-Socket/
├── pyproject.toml          # uv-managed, created in Task 1
├── task1/
│   ├── server0.py          # TCP echo server, created in Task 2
│   └── client0.py          # TCP echo client, created in Task 3
├── README.md               # existing
└── docs/
```

---

### Task 1: Project Setup

**Files:**
- Create: `pyproject.toml` (via `uv init`)
- Create: `task1/` directory

- [ ] **Step 1: Initialize project with uv**

Run `uv init --name hzcu-socket` from the project root. This creates `pyproject.toml` with the project name.

- [ ] **Step 2: Add dependencies**

Run `uv add loguru rich questionary` to install the three required packages. This updates `pyproject.toml` and generates `uv.lock`.

- [ ] **Step 3: Create task1 directory**

Run `mkdir -p task1`.

- [ ] **Step 4: Clean up uv scaffold**

Remove any default files `uv init` may have created (e.g. `main.py`, `hello.py`).

---

### Task 2: TCP Echo Server

**Files:**
- Create: `task1/server0.py`

- [ ] **Step 1: Implement server0.py**

Create the server script with these requirements:

- Imports: `socket`, `threading`, `loguru`, `rich.console.Console`
- Constants: `HOST = "0.0.0.0"`, `PORT = 9000`, `ENCODING = "utf-8"`, `BUFFER_SIZE = 4096`
- Configure loguru to print via rich console with green timestamps and aligned log levels
- `handle_client(conn, addr)`: receive loop that decodes messages, logs them, echoes back via `sendall`, catches `ConnectionResetError`/`OSError`, and closes the socket on exit
- `main()`: create TCP socket, set `SO_REUSEADDR`, bind, listen (backlog 5), accept loop that spawns a daemon thread per client, graceful shutdown on `KeyboardInterrupt`

- [ ] **Step 2: Verify server starts**

Run `uv run task1/server0.py` in a terminal. The server should log its listening address and wait for connections. Ctrl+C should produce a clean shutdown log.

---

### Task 3: TCP Echo Client

**Files:**
- Create: `task1/client0.py`

- [ ] **Step 1: Implement client0.py**

Create the client script with these requirements:

- Imports: `socket`, `questionary`, `loguru`, `rich.console.Console`, `rich.panel.Panel`
- Constants: `HOST = "127.0.0.1"`, `PORT = 9000`, `ENCODING = "utf-8"`, `BUFFER_SIZE = 4096`
- Configure loguru the same way as the server
- `main()`: connect to server, log success, enter interactive loop using `questionary.text()` for input, break on empty/quit/exit, send via `sendall`, receive and display in a `rich.panel.Panel` with title "Server Echo", catch `ConnectionResetError`/`BrokenPipeError`, close socket on exit

- [ ] **Step 2: Verify client behavior without server**

Run `uv run task1/client0.py` without starting the server. It should log a connection error and exit cleanly.

---

### Task 4: Integration Test

**Files:** None

- [ ] **Step 1: Start server and connect one client**

Run the server in Terminal 1, then the client in Terminal 2. Type a message in the client — it should be echoed back and displayed in a rich panel. The server log should show the connect event and message traffic.

- [ ] **Step 2: Test concurrent clients**

Start a second client in Terminal 3. Send messages from both clients. The server should handle both independently, with interleaved log entries.

- [ ] **Step 3: Test graceful disconnect**

Type `quit` in one client (or Ctrl+C). The server should log the disconnection and keep running for the other client.

- [ ] **Step 4: Test server shutdown**

Ctrl+C the server. Remaining clients should get connection errors and exit.

---

### Task 5: Commit

- [ ] **Step 1: Commit completed Task 1**

Stage `pyproject.toml`, `uv.lock`, `task1/server0.py`, `task1/client0.py` and commit with message `feat(task1): implement basic TCP echo server and client`.
