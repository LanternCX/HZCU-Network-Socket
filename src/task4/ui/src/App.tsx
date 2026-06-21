import {
  CircleHelp,
  FileImage,
  FolderUp,
  Globe2,
  Image,
  Info,
  Mail,
  MessageCircle,
  MoreHorizontal,
  Paperclip,
  Plus,
  Search,
  Send,
  Settings,
  Smile,
  Trash2,
  Users,
} from 'lucide-react';
import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import './styles.css';

export type BridgeEvent =
  | { type: 'connected'; username?: string }
  | { type: 'message'; sender?: string; text: string }
  | { type: 'room_message'; room?: string; sender?: string; text: string }
  | { type: 'private_message'; sender?: string; text: string }
  | { type: 'system'; text: string }
  | { type: 'users'; users: string[] }
  | { type: 'rooms'; rooms: string[] }
  | { type: 'room_info'; room: string; participants?: number; creator?: string }
  | { type: 'file_received'; filename: string; mimeType: string; path: string; sender?: string }
  | { type: 'error'; text: string }
  | { type: 'disconnected'; text?: string };

type UiEvent =
  | { type: 'connect'; username: string }
  | { type: 'message'; scope: 'room' | 'public'; text: string }
  | { type: 'command'; text: string }
  | { type: 'join_room'; room: string }
  | { type: 'create_room'; room: string }
  | { type: 'delete_room'; room: string }
  | { type: 'leave_room' }
  | { type: 'private_message'; target: string; text: string }
  | { type: 'request_users' }
  | { type: 'request_help' }
  | {
      type: 'send_file';
      filename: string;
      mimeType: string;
      sender: string;
      scope: string;
      target: string;
      payload: string;
    };

type AppProps = {
  sendEvent?: (event: UiEvent) => void;
  initialEvents?: BridgeEvent[];
  connectedUsername?: string;
};

type ChatItem = {
  id: string;
  type: 'message' | 'system' | 'file' | 'error';
  channel: 'public' | 'private';
  sender?: string;
  text?: string;
  filename?: string;
  mimeType?: string;
  path?: string;
  time: string;
};

const initialRooms = ['general'];
type ActiveView = 'public' | 'private' | 'rooms' | 'help';

function nowLabel() {
  return new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date());
}

function eventToChatItem(event: BridgeEvent): ChatItem | null {
  if (event.type === 'message' || event.type === 'room_message' || event.type === 'private_message') {
    return {
      id: crypto.randomUUID(),
      type: 'message',
      channel: event.type === 'private_message' ? 'private' : 'public',
      sender: event.sender || 'Server',
      text: event.text,
      time: nowLabel(),
    };
  }
  if (event.type === 'system') {
    return {
      id: crypto.randomUUID(),
      type: 'system',
      channel: 'public',
      text: event.text,
      time: nowLabel(),
    };
  }
  if (event.type === 'file_received') {
    return {
      id: crypto.randomUUID(),
      type: 'file',
      channel: 'public',
      sender: event.sender || 'Server',
      filename: event.filename,
      mimeType: event.mimeType,
      path: event.path,
      time: nowLabel(),
    };
  }
  if (event.type === 'error') {
    return {
      id: crypto.randomUUID(),
      type: 'error',
      channel: 'public',
      text: event.text,
      time: nowLabel(),
    };
  }
  return null;
}

export default function App({ sendEvent, initialEvents = [], connectedUsername = '' }: AppProps) {
  const [currentUser, setCurrentUser] = useState(connectedUsername);
  const [isChatStarted, setIsChatStarted] = useState(Boolean(connectedUsername));
  const [users, setUsers] = useState<string[]>(connectedUsername ? [connectedUsername] : []);
  const [rooms, setRooms] = useState(initialRooms);
  const [room, setRoom] = useState('general');
  const [participants, setParticipants] = useState(connectedUsername ? 1 : 0);
  const [creator, setCreator] = useState('');
  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [activeView, setActiveView] = useState<ActiveView>('public');
  const [privateTarget, setPrivateTarget] = useState('');
  const [roomDraft, setRoomDraft] = useState('new-room');
  const [input, setInput] = useState('');
  const [query, setQuery] = useState('');
  const [connectionText, setConnectionText] = useState(connectedUsername ? 'Connected to server' : 'Not connected');
  const socketRef = useRef<WebSocket | null>(null);

  const emit = (event: UiEvent) => {
    if (sendEvent) {
      sendEvent(event);
      return;
    }
    socketRef.current?.send(JSON.stringify(event));
  };

  const applyBridgeEvent = (event: BridgeEvent) => {
    if (event.type === 'users') {
      setUsers((current) => {
        const merged = [...event.users];
        if (currentUser && !merged.includes(currentUser)) {
          merged.unshift(currentUser);
        }
        return merged;
      });
    }
    if (event.type === 'rooms') {
      setRooms(event.rooms.length > 0 ? event.rooms : initialRooms);
    }
    if (event.type === 'room_info') {
      setRoom(event.room);
      setParticipants(event.participants ?? participants);
      setCreator(event.creator || creator);
      setRooms((current) => (current.includes(event.room) ? current : [...current, event.room]));
    }
    if (event.type === 'connected') {
      const connectedName = event.username || currentUser;
      if (connectedName) {
        setCurrentUser(connectedName);
        setUsers((current) => (current.includes(connectedName) ? current : [connectedName, ...current]));
      }
      setIsChatStarted(true);
      setConnectionText('Connected to server');
    }
    if (event.type === 'disconnected') {
      setConnectionText(event.text || 'Disconnected from server');
    }
    const item = eventToChatItem(event);
    if (item) {
      setMessages((current) => [...current, item]);
    }
  };

  useEffect(() => {
    if (isChatStarted) {
      initialEvents.forEach(applyBridgeEvent);
    }
  }, []);

  const openSocket = (username: string) => {
    if (sendEvent || typeof WebSocket === 'undefined') {
      return;
    }
    const socketProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${socketProtocol}://${window.location.host}`);
    socketRef.current = socket;
    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({ type: 'connect', username }));
    });
    socket.addEventListener('message', (message) => {
      applyBridgeEvent(JSON.parse(message.data));
    });
    socket.addEventListener('close', () => setConnectionText('Disconnected from server'));
    socket.addEventListener('error', () => {
      applyBridgeEvent({ type: 'error', text: 'WebSocket connection failed.' });
    });
  };

  useEffect(() => () => socketRef.current?.close(), []);

  const filteredUsers = useMemo(
    () => users.filter((user) => user.toLowerCase().includes(query.toLowerCase())),
    [query, users],
  );

  const visibleMessages = useMemo(
    () => messages.filter((message) => (activeView === 'private' ? message.channel === 'private' : message.channel === 'public')),
    [activeView, messages],
  );

  const openPublicChat = () => setActiveView('public');

  const openPrivateMessages = (target = privateTarget) => {
    setActiveView('private');
    if (target) {
      setPrivateTarget(target);
    }
    emit({ type: 'request_users' });
  };

  const openRoomList = () => setActiveView('rooms');

  const selectableUsers = useMemo(
    () => users.filter((user) => user !== currentUser),
    [currentUser, users],
  );

  const createRoom = (roomName: string) => {
    const trimmedRoom = roomName.trim();
    if (!trimmedRoom) {
      return;
    }
    emit({ type: 'create_room', room: trimmedRoom });
  };

  const deleteRoom = (roomName: string) => {
    emit({ type: 'delete_room', room: roomName });
    setRooms((current) => current.filter((candidate) => candidate !== roomName));
    if (room === roomName) {
      setRoom('general');
    }
  };

  const openHelp = () => {
    setActiveView('help');
    emit({ type: 'request_help' });
  };

  const joinRoom = (roomName: string) => {
    setActiveView('public');
    setRoom(roomName);
    emit({ type: 'join_room', room: roomName });
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const text = input.trim();
    if (!text) {
      return;
    }
    if (text.startsWith('/')) {
      emit({ type: 'command', text });
    } else if (activeView === 'private' && privateTarget) {
      emit({ type: 'private_message', target: privateTarget, text });
    } else {
      emit({ type: 'message', scope: 'room', text });
    }
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        type: 'message',
        channel: activeView === 'private' && privateTarget ? 'private' : 'public',
        sender: `${currentUser} (You)`,
        text,
        time: nowLabel(),
      },
    ]);
    setInput('');
  };

  const startChat = (rawUsername: string | null) => {
    const username = rawUsername?.trim() || "";
    if (!username) {
      return;
    }
    setCurrentUser(username);
    setUsers([username]);
    setParticipants(1);
    setIsChatStarted(true);
    setConnectionText('Connecting to server');
    emit({ type: 'connect', username });
    openSocket(username);
  };

  useEffect(() => {
    if (isChatStarted) {
      return;
    }
    startChat(window.prompt('Enter your username:'));
  }, []);

  const encodeFile = async (file: File) => {
    const buffer = await new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader();
      reader.addEventListener('load', () => resolve(reader.result as ArrayBuffer));
      reader.addEventListener('error', () => reject(reader.error));
      reader.readAsArrayBuffer(file);
    });
    let binary = '';
    const bytes = new Uint8Array(buffer);
    bytes.forEach((byte) => {
      binary += String.fromCharCode(byte);
    });
    return btoa(binary);
  };

  const handleFileSelect = async (file: File | undefined) => {
    if (!file) {
      return;
    }
    const mimeType = file.type || 'application/octet-stream';
    const payload = await encodeFile(file);
    emit({
      type: 'send_file',
      filename: file.name,
      mimeType,
      sender: currentUser,
      scope: 'room',
      target: room,
      payload,
    });
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        type: 'file',
        channel: 'public',
        sender: `${currentUser} (You)`,
        filename: file.name,
        mimeType,
        path: `data:${mimeType};base64,${payload}`,
        time: nowLabel(),
      },
    ]);
  };

  return (
    <div className="app-shell">
      <header className="titlebar">
        <div className="brand">
          <MessageCircle size={22} />
          <span>LAN Chat</span>
          <strong>(Step 4) - Graphical Chat System</strong>
        </div>
        <div className="window-actions" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </header>

      {isChatStarted ? (

      <div className="workspace">
        <aside className="sidebar">
          <section className="profile-card">
            <div className="avatar avatar-large">{currentUser.slice(0, 1).toUpperCase()}</div>
            <div>
              <h1>{currentUser}</h1>
              <p><span className="status-dot" />Online</p>
            </div>
          </section>

          <nav aria-label="Main menu" className="menu">
            <p className="section-label">MENU</p>
            <button className={`menu-item ${activeView === 'public' ? 'active' : ''}`} onClick={openPublicChat}><Globe2 />Public Chat</button>
            <button className={`menu-item ${activeView === 'private' ? 'active' : ''}`} onClick={() => openPrivateMessages(privateTarget || selectableUsers[0] || '')}><Mail />Private Messages</button>
            <button className={`menu-item ${activeView === 'rooms' ? 'active' : ''}`} onClick={openRoomList}><Users />Rooms</button>
            <button className={`menu-item ${activeView === 'help' ? 'active' : ''}`} onClick={openHelp}><CircleHelp />Help</button>
          </nav>

          <section className="rooms">
            <div className="rooms-heading">
              <p className="section-label">MY ROOMS</p>
              <button aria-label="Create room" onClick={openRoomList}><Plus /></button>
            </div>
            {rooms.map((roomName, index) => (
              <button
                key={roomName}
                className={`room-item ${roomName === room ? 'active' : ''}`}
                onClick={() => joinRoom(roomName)}
              >
                <span className={`hash hash-${index}`}>#</span>{roomName}
              </button>
            ))}
          </section>

          <section className="connection-card">
            <p><span className="status-dot" />{connectionText}</p>
            <span>192.168.1.100:9003</span>
            <Settings aria-label="Settings" />
          </section>
        </aside>

        <main aria-label="Chat room" className="chat-panel">
          <header className="chat-header">
            <div className="room-icon">#</div>
            <div>
              <h2>
                {activeView === 'private' ? 'Private Messages' : activeView === 'rooms' ? 'Rooms' : activeView === 'help' ? 'Help' : room}
              </h2>
              <p>
                {activeView === 'private' && privateTarget ? `Chat with ${privateTarget}` : activeView === 'public' ? `${participants} participants` : connectionText}
              </p>
            </div>
            <div className="chat-actions">
              <button aria-label="Room users"><Users /></button>
              <button aria-label="Room information"><Info /></button>
              <button aria-label="More actions"><MoreHorizontal /></button>
            </div>
          </header>

          {activeView === 'rooms' ? (
            <section className="visit-panel" aria-label="Rooms panel">
              <div className="visit-panel-header">
                <h2>Rooms</h2>
                <div className="room-actions">
                  <label>
                    <span className="sr-only">Room name</span>
                    <input
                      aria-label="Room name"
                      value={roomDraft}
                      onChange={(event) => setRoomDraft(event.target.value)}
                    />
                  </label>
                  <button type="button" aria-label="Create room" onClick={() => createRoom(roomDraft)}>
                    <Plus size={16} />
                    Create
                  </button>
                </div>
              </div>
              {rooms.map((roomName, index) => (
                <div key={roomName} className="visit-row room-visit-row">
                  <button type="button" className="room-link" aria-label={roomName} onClick={() => joinRoom(roomName)}>
                    <span className={`hash hash-${index}`}>#</span>
                    <span>{roomName}</span>
                  </button>
                  <button type="button" className="room-command" aria-label={`Join ${roomName}`} onClick={() => joinRoom(roomName)}>
                    Join
                  </button>
                  {roomName !== 'general' ? (
                    <button type="button" className="room-command danger" aria-label={`Delete ${roomName}`} onClick={() => deleteRoom(roomName)}>
                      <Trash2 size={16} />
                    </button>
                  ) : null}
                </div>
              ))}
            </section>
          ) : activeView === 'private' ? (
            <section className="private-panel" aria-label="Private messages panel">
              <aside className="online-panel private-users">
                <h2>ONLINE USERS</h2>
                <label className="search-box">
                  <Search size={18} />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search users..."
                  />
                </label>
                <div className="user-list">
                  {filteredUsers.filter((user) => user !== currentUser).map((user, index) => (
                    <button
                      key={user}
                      type="button"
                      className={`user-row ${privateTarget === user ? 'active' : ''}`}
                      aria-label={user}
                      onClick={() => setPrivateTarget(user)}
                    >
                      <span className={`avatar avatar-${index % 5}`}>{user.slice(0, 1).toUpperCase()}</span>
                      <span className="status-dot" />
                      <span>{user}</span>
                    </button>
                  ))}
                </div>
              </aside>
              <div className="private-messages">
                {visibleMessages.map((message) => (
                  <article key={message.id} className={`message-row ${message.type}`}>
                    <div className="avatar">{message.sender?.slice(0, 1).toUpperCase() || 'U'}</div>
                    <div className="message-body">
                      <strong>{message.sender}</strong>
                      <p>{message.text}</p>
                    </div>
                    <time>{message.time}</time>
                  </article>
                ))}
              </div>
            </section>
          ) : activeView === 'help' ? (
            <section className="visit-panel" aria-label="Help panel">
              <h2>Help</h2>
              <p>/pm user message</p>
              <p>/create room</p>
              <p>/delete room</p>
              <p>/join room</p>
              <p>/leave</p>
              <p>/room message</p>
              <p>/list</p>
              <p>/help</p>
            </section>
          ) : (
          <section className="message-list" aria-label="Messages">
            {visibleMessages.map((message) => (
              <article key={message.id} className={`message-row ${message.type}`}>
                {message.type === 'system' || message.type === 'error' ? (
                  <p className="system-text">{message.text}</p>
                ) : (
                  <>
                    <div className="avatar">{message.sender?.slice(0, 1).toUpperCase() || 'U'}</div>
                    <div className="message-body">
                      <strong>{message.sender}</strong>
                      {message.type === 'file' && message.mimeType?.startsWith('image/') ? (
                        <img src={message.path} alt={message.filename} className="received-image" />
                      ) : message.type === 'file' ? (
                        <a href={message.path} className="file-chip">
                          <FolderUp size={16} />
                          {message.filename}
                        </a>
                      ) : (
                        <p>{message.text}</p>
                      )}
                    </div>
                  </>
                )}
                <time>{message.time}</time>
              </article>
            ))}
          </section>
          )}

          <form className="composer" onSubmit={handleSubmit}>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Type a message..."
              aria-label="Message"
            />
            <button type="submit" className="send-button" aria-label="Send message">
              <Send size={18} />
              Send
            </button>
            <div className="composer-tools">
              <button type="button" aria-label="Choose emoticon"><Smile /></button>
              <label aria-label="Send image">
                <Image />
                <input type="file" accept="image/*" onChange={(event) => handleFileSelect(event.target.files?.[0])} />
              </label>
              <label aria-label="Send file">
                <Paperclip />
                <input type="file" onChange={(event) => handleFileSelect(event.target.files?.[0])} />
                  </label>
              <span>Commands: /pm /create /delete /join /room /list /help</span>
            </div>
          </form>
        </main>

        <aside aria-label="Online users and room info" className="details-panel">
          <section className="online-panel">
            <h2>ONLINE USERS</h2>
            <label className="search-box">
              <Search size={18} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search users..."
              />
            </label>
            <div className="user-list">
              {filteredUsers.map((user, index) => (
                <button
                  key={user}
                  className="user-row"
                  aria-label={user}
                  onClick={() => openPrivateMessages(user)}
                >
                  <span className={`avatar avatar-${index % 5}`}>{user.slice(0, 1).toUpperCase()}</span>
                  <span className="status-dot" />
                  <span>{user}{user === currentUser ? ' (You)' : ''}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="room-info">
            <h2>ROOM INFO</h2>
            <p>Room: {room}</p>
            {creator ? <p>Created by: {creator}</p> : null}
            <p>Participants: {participants}</p>
            <div className="file-hint"><FileImage /> Images and files appear in the chat stream.</div>
          </section>
        </aside>
      </div>
      ) : null}
    </div>
  );
}
