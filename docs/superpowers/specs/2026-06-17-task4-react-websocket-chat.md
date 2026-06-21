# Status: Draft

# Task 4 React WebSocket Chat Spec

## Scope

Task 4 implements a graphical LAN chat tool while preserving the socket TCP communication model from the earlier tasks.

The system uses this architecture:

```text
React web UI <--WebSocket--> client3.py <--TCP socket--> server3.py
```

The React UI is the graphical client shown to the user. `client3.py` is a combined browser-facing client process: it accepts WebSocket connections from the web UI and maintains a TCP socket connection to `server3.py`. `server3.py` is the socket TCP chat server and owns the main chat behavior.

The UI should follow `docs/superpowers/specs/UI Design.png`.

## Goals

- Keep all task 3 chat features: public chat, private messages, rooms, online users, and slash commands.
- Add a React graphical interface based on the provided UI design.
- Use WebSocket for communication between the web UI and `client3.py`.
- Use TCP socket communication between `client3.py` and `server3.py`.
- Support file transfer and image/emoticon sending.
- Show received files and images in the UI.
- Store received files and images locally so they can be inspected after transfer.
- Keep slash commands available while also offering UI controls for common actions.
- Include tests for the React UI behavior.

## Non-Goals

- Do not replace the TCP socket server with a WebSocket-only chat server.
- Do not build a separate WebSocket gateway file outside `client3.py`.
- Do not require a database.
- Do not add login accounts or passwords.
- Do not redesign the UI away from the provided image.

## Components

### React Web UI

The React app provides the graphical chat interface.

It should include:

- Left sidebar with current user, online status, menu items, joined rooms, and connection status.
- Center chat panel with current room title, participant count, message history, and message composer.
- Right panel with online user list and room information.
- Composer controls for text messages, image/emoticon sending, file sending, and send action.
- Search field for filtering online users.
- Help view or help panel for available commands.

The UI keeps the layout and intent of `UI Design.png`:

- App-window style frame.
- Three-column layout.
- Active room selection in the left sidebar.
- Message stream in the center.
- Online users and room details on the right.
- Bottom input area with text field, attachment controls, and command hint text.

### client3.py

`client3.py` acts as the task 4 client.

It has two responsibilities in one process:

- WebSocket side: communicate with the React UI.
- TCP side: communicate with `server3.py` using raw socket TCP.

It should:

- Start a WebSocket endpoint for the React app.
- Connect to `server3.py` as a TCP socket client.
- Send the selected username to `server3.py`.
- Forward normal chat messages and slash commands from the UI to `server3.py`.
- Translate UI actions into command-style TCP messages when useful.
- Forward messages, room events, online user updates, file events, and errors from `server3.py` back to the UI.
- Store received files/images locally under a task-specific receive directory.
- Tell the UI where stored received files/images can be displayed or downloaded.

Common UI-to-command translations:

- Join room button: `/join <room>`
- Create room action: `/create <room>`
- Leave room action: `/leave`
- Private message action: `/pm <user> <message>`
- Room message action: `/room <message>`
- Online users refresh: `/list`
- Help button: `/help`

The text input still accepts the same slash commands directly.

### server3.py

`server3.py` is the task 4 socket TCP server.

It should build on the task 3 server behavior and add file/image transfer.

It should support:

- Multiple concurrent clients.
- Public chat broadcast.
- Private messages.
- Room creation, joining, leaving, and room messages.
- Online user listing.
- Help text.
- File transfer with metadata and binary content.
- Image/emoticon transfer using the same file transfer path with image-aware metadata.
- Local storage of received files/images on the receiving client side through `client3.py`.

## Communication Design

### Web UI to client3.py

The React UI communicates with `client3.py` over WebSocket.

Messages should use structured JSON so the UI can avoid parsing raw terminal text for normal actions.

Recommended client-to-`client3.py` event types:

- `connect`: choose username and server connection settings.
- `message`: send a public or current-room text message.
- `command`: send a raw slash command.
- `join_room`: join a room.
- `create_room`: create a room.
- `leave_room`: leave the current room.
- `private_message`: send a private message.
- `send_file`: send a file or image.
- `request_users`: request the online user list.
- `request_help`: request help text.

Recommended `client3.py`-to-client event types:

- `connected`: WebSocket and TCP connection are ready.
- `message`: chat message for display.
- `system`: server/system notice.
- `private_message`: private message event.
- `room_message`: room message event.
- `users`: online user list.
- `rooms`: room list or joined room state.
- `room_info`: active room details.
- `file_received`: received file/image metadata and local display path.
- `error`: user-facing error message.
- `disconnected`: connection closed or lost.

### client3.py to server3.py

`client3.py` communicates with `server3.py` over raw TCP socket.

Text commands should remain compatible with task 3:

- `/pm <user> <message>`
- `/create <room>`
- `/join <room>`
- `/leave`
- `/room <message>`
- `/list`
- `/help`

File and image transfer should use a clear protocol with:

- A command/header message describing the transfer.
- File name.
- File size.
- File type or MIME type when available.
- Sender.
- Optional room or target user.
- Binary payload.

The protocol must avoid confusing file bytes with normal chat text. The exact header format can be finalized during implementation, but it must be deterministic and easy to test.

## File and Image Behavior

Files and images are both transferred through the same file transfer system.

The UI should:

- Let the user choose a file from the composer.
- Let the user choose an image/emoticon from the composer.
- Show upload progress or at least a sending state.
- Display received images inline in the chat stream.
- Display received non-image files as downloadable/openable file items.
- Show sender, file name, size, and timestamp.

`client3.py` should:

- Store received files/images locally.
- Keep received content in a task-specific directory, such as `data/task4/received/`.
- Use safe file names to avoid overwriting unrelated files.
- Report saved file metadata to the UI.

`server3.py` should:

- Route files/images to the correct recipients.
- Support room file sharing.
- Support private file sharing if private messages are implemented through the same transfer path.
- Reject invalid or incomplete file transfers gracefully.

## UI Behavior

### Startup

The user opens the React app, enters or confirms a username, and connects through `client3.py`.

After connection:

- The left sidebar shows the current user and online status.
- The center panel opens the default public chat or selected room.
- The right panel shows online users and active room information.
- The bottom status area shows the TCP server connection target.

### Messaging

The user can send:

- Public messages.
- Room messages.
- Private messages.
- Slash commands typed directly into the input.
- Files.
- Images/emoticons.

The UI should append local sent messages and display incoming messages in chronological order.

### Rooms

The user can:

- Create a room.
- Join a room.
- Leave a room.
- Select rooms from the sidebar.
- See room name, creator if available, creation time if available, and participant count if available.

If some room metadata is not available from `server3.py`, the UI should show only the confirmed fields instead of fake values.

### Online Users

The right panel shows online users.

The UI should:

- Mark the current user.
- Show online status.
- Support search/filter.
- Allow starting a private message from a user entry.

### Help

The Help menu should show supported slash commands and short descriptions.

The help content should match the commands actually supported by `server3.py`.

## Error Handling

The UI should show clear user-facing errors for:

- WebSocket connection failure.
- TCP server connection failure.
- Username rejected or unavailable, if that validation is added.
- Unknown command.
- Room not found.
- User not found.
- File too large.
- File transfer interrupted.
- Server disconnected.

`client3.py` should keep the UI informed when either side of the bridge disconnects.

`server3.py` should avoid one client failure affecting other clients.

## Storage

Use task-specific runtime storage paths.

Recommended paths:

- `data/task4/received/` for received files/images.
- `data/task4/sent/` only if a local sent-file copy is needed.

Generated runtime files should not be committed.

## Testing

Testing should focus on behavior and regression coverage.

Recommended tests:

- Task 3 command behavior still works in `server3.py`.
- `client3.py` translates WebSocket UI actions into the expected TCP commands.
- Slash commands pass through unchanged.
- File transfer metadata is parsed correctly.
- Received files are stored under the task 4 receive directory.
- Invalid file headers fail without crashing the server.
- Online user list events can be converted into UI-friendly data.
- React UI renders the main layout from the provided design: side menu, chat panel, online users panel, room info panel, and message composer.
- React UI sends the expected WebSocket events for text messages, slash commands, room actions, private messages, and file/image selection.
- React UI displays received chat messages, system notices, online users, room details, inline images, and file items from WebSocket events.
- React UI shows connection and transfer errors clearly.

Manual verification should include:

- Start `server3.py`.
- Start `client3.py`.
- Start the React UI.
- Connect at least two browser clients or browser sessions.
- Send public chat messages.
- Create and join rooms.
- Send room messages.
- Send private messages.
- Use slash commands directly.
- Send and receive an image.
- Send and receive a non-image file.
- Confirm received files are visible in the UI and stored locally.

## Implementation Boundaries

Recommended file layout:

```text
src/task4/server3.py
src/task4/client3.py
src/task4/ui/
tests/test_task4_server.py
tests/test_task4_client_bridge.py
```

The React app should live under `src/task4/ui/`.

The task 4 implementation should avoid changing task 1, task 2, or task 3 behavior unless shared cleanup is required and covered by tests.

## Acceptance Criteria

Task 4 is complete when:

- The React UI follows the provided UI design closely.
- The system uses `web <--WebSocket--> client3.py <--TCP socket--> server3.py`.
- Existing task 3 commands remain usable.
- UI controls exist for common actions.
- Multiple users can chat through the graphical UI.
- Rooms and private messages work through the graphical UI.
- Files and images can be sent, received, displayed, and stored locally.
- Connection and transfer errors are shown clearly.
- Behavior tests cover command compatibility, client-side translation, and file handling.
- Manual LAN-style verification steps are documented for the experiment report.
