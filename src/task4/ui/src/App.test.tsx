import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';

afterEach(() => {
  cleanup();
});

describe('Task 4 React UI', () => {
  it('asks for a username with a browser prompt before showing chat', () => {
    vi.spyOn(window, 'prompt').mockReturnValue('');
    render(<App sendEvent={vi.fn()} />);

    expect(screen.getByText('LAN Chat')).toBeInTheDocument();
    expect(window.prompt).toHaveBeenCalledWith('Enter your username:');
    expect(screen.queryByRole('main', { name: 'Chat room' })).not.toBeInTheDocument();
  });

  it('renders the chat design with the right-side online users panel after username is set', async () => {
    const send = vi.fn();
    vi.spyOn(window, 'prompt').mockReturnValue('Carol');
    render(<App sendEvent={send} />);

    expect(send).toHaveBeenCalledWith({ type: 'connect', username: 'Carol' });
    expect(screen.getByRole('navigation', { name: 'Main menu' })).toBeInTheDocument();
    expect(screen.getByRole('main', { name: 'Chat room' })).toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: 'Online users and room info' })).toBeInTheDocument();
    expect(screen.getByText('ONLINE USERS')).toBeInTheDocument();
    expect(screen.getByText('ROOM INFO')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Type a message...')).toBeInTheDocument();
  });

  it('does not show demo messages or demo online users', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('Carol');
    render(<App sendEvent={vi.fn()} />);

    expect(screen.queryByText('Hello everyone!')).not.toBeInTheDocument();
    expect(screen.queryByText('Bob')).not.toBeInTheDocument();
    expect(screen.getByText('Carol (You)')).toBeInTheDocument();
  });

  it('sends text and slash commands as websocket events', async () => {
    const send = vi.fn();
    vi.spyOn(window, 'prompt').mockReturnValue('Carol');
    render(<App sendEvent={send} />);
    send.mockClear();
    const input = screen.getByPlaceholderText('Type a message...');

    await userEvent.type(input, 'Hello everyone');
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }));
    await userEvent.type(input, '/join study');
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }));

    expect(send).toHaveBeenNthCalledWith(1, {
      type: 'message',
      scope: 'room',
      text: 'Hello everyone',
    });
    expect(send).toHaveBeenNthCalledWith(2, {
      type: 'command',
      text: '/join study',
    });
  });

  it('sends selected files with content payloads', async () => {
    const send = vi.fn();
    vi.spyOn(window, 'prompt').mockReturnValue('Carol');
    render(<App sendEvent={send} />);
    send.mockClear();
    const file = new File(['saved content'], 'notes.txt', { type: 'text/plain' });

    await userEvent.upload(screen.getByLabelText('Send file'), file);

    await waitFor(() => {
      expect(send).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'send_file',
          filename: 'notes.txt',
          mimeType: 'text/plain',
          payload: 'c2F2ZWQgY29udGVudA==',
          sender: 'Carol',
          target: 'general',
        }),
      );
    });
  });

  it('shows selected images and files in the chat immediately', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('Carol');
    render(<App sendEvent={vi.fn()} />);
    const image = new File(['image content'], 'photo.png', { type: 'image/png' });
    const file = new File(['saved content'], 'notes.txt', { type: 'text/plain' });

    await userEvent.upload(screen.getByLabelText('Send image'), image);
    await userEvent.upload(screen.getByLabelText('Send file'), file);

    expect(await screen.findByAltText('photo.png')).toBeInTheDocument();
    expect(screen.getByText('notes.txt')).toBeInTheDocument();
  });

  it('renders incoming images, file items, users, room details, and errors', () => {
    render(
      <App
        connectedUsername="Alice"
        initialEvents={[
          { type: 'users', users: ['Alice', 'Bob'] },
          { type: 'room_info', room: 'general', participants: 2, creator: 'Alice' },
          {
            type: 'file_received',
            filename: 'diagram.png',
            mimeType: 'image/png',
            path: '/files/diagram.png',
            sender: 'Bob',
          },
          {
            type: 'file_received',
            filename: 'notes.pdf',
            mimeType: 'application/pdf',
            path: '/files/notes.pdf',
            sender: 'Carol',
          },
          { type: 'error', text: 'File transfer interrupted.' },
        ]}
      />,
    );

    expect(screen.getAllByText('Bob').length).toBeGreaterThan(0);
    expect(screen.getByAltText('diagram.png')).toBeInTheDocument();
    expect(screen.getByText('notes.pdf')).toBeInTheDocument();
    expect(screen.getByText('File transfer interrupted.')).toBeInTheDocument();
  });

  it('keeps private messages out of the public chat until private messages are opened', async () => {
    render(
      <App
        connectedUsername="Alice"
        initialEvents={[
          { type: 'message', sender: 'Bob', text: 'Public hello' },
          { type: 'private_message', sender: 'Bob', text: 'Secret hello' },
        ]}
      />,
    );

    expect(screen.getByText('Public hello')).toBeInTheDocument();
    expect(screen.queryByText('Secret hello')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Private Messages' }));

    expect(screen.getByText('Secret hello')).toBeInTheDocument();
    expect(screen.queryByText('Public hello')).not.toBeInTheDocument();
  });

  it('lets the private messages and rooms menu items open their matching panels', async () => {
    const send = vi.fn();
    render(
      <App
        sendEvent={send}
        connectedUsername="Alice"
        initialEvents={[
          { type: 'users', users: ['Alice', 'Bob'] },
          { type: 'room_info', room: 'general', participants: 2, creator: 'Alice' },
        ]}
      />,
    );

    expect(screen.queryByRole('button', { name: 'Online Users' })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Private Messages' }));
    expect(send).toHaveBeenCalledWith({ type: 'request_users' });
    const privatePanel = screen.getByRole('region', { name: 'Private messages panel' });
    await userEvent.click(within(privatePanel).getByRole('button', { name: 'Bob' }));
    expect(screen.getByRole('heading', { name: 'Private Messages' })).toBeInTheDocument();
    expect(screen.getByText('Chat with Bob')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Rooms' }));
    const roomsPanel = screen.getByRole('region', { name: 'Rooms panel' });
    expect(within(roomsPanel).getByRole('heading', { name: 'Rooms' })).toBeInTheDocument();
  });

  it('opens the room form from the sidebar add button instead of creating a duplicate hidden room', async () => {
    const send = vi.fn();
    render(<App sendEvent={send} connectedUsername="Alice" />);

    await userEvent.click(screen.getByRole('button', { name: 'Create room' }));

    expect(screen.getByRole('region', { name: 'Rooms panel' })).toBeInTheDocument();
    expect(screen.getByLabelText('Room name')).toBeInTheDocument();
    expect(send).not.toHaveBeenCalledWith({ type: 'create_room', room: 'new-room' });
  });

  it('updates the room panel automatically and exposes room command buttons', async () => {
    const send = vi.fn();
    render(
      <App
        sendEvent={send}
        connectedUsername="Alice"
        initialEvents={[
          { type: 'room_info', room: 'general', participants: 2, creator: 'Alice' },
          { type: 'room_info', room: 'study', participants: 1, creator: 'Bob' },
        ]}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Rooms' }));
    const roomsPanel = screen.getByRole('region', { name: 'Rooms panel' });
    expect(within(roomsPanel).getByRole('button', { name: 'general' })).toBeInTheDocument();
    expect(within(roomsPanel).getByRole('button', { name: 'study' })).toBeInTheDocument();

    await userEvent.clear(within(roomsPanel).getByLabelText('Room name'));
    await userEvent.type(within(roomsPanel).getByLabelText('Room name'), 'lab');
    await userEvent.click(within(roomsPanel).getByRole('button', { name: 'Create room' }));
    expect(send).toHaveBeenCalledWith({ type: 'create_room', room: 'lab' });

    await userEvent.click(within(roomsPanel).getByRole('button', { name: 'Join general' }));
    expect(send).toHaveBeenCalledWith({ type: 'join_room', room: 'general' });

    await userEvent.click(screen.getByRole('button', { name: 'Rooms' }));
    const refreshedRoomsPanel = screen.getByRole('region', { name: 'Rooms panel' });
    expect(within(refreshedRoomsPanel).queryByRole('button', { name: 'Leave current room' })).not.toBeInTheDocument();

    await userEvent.click(within(refreshedRoomsPanel).getByRole('button', { name: 'Delete study' }));
    expect(send).toHaveBeenCalledWith({ type: 'delete_room', room: 'study' });
  });

  it('shows online user rows in private messages and sends to the selected user', async () => {
    const send = vi.fn();
    render(
      <App
        sendEvent={send}
        connectedUsername="Alice"
        initialEvents={[{ type: 'users', users: ['Alice', 'Bob', 'Carol'] }]}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Private Messages' }));
    expect(send).toHaveBeenCalledWith({ type: 'request_users' });
    const privatePanel = screen.getByRole('region', { name: 'Private messages panel' });
    expect(within(privatePanel).getByRole('heading', { name: 'ONLINE USERS' })).toBeInTheDocument();
    expect(within(privatePanel).getByPlaceholderText('Search users...')).toBeInTheDocument();
    await userEvent.click(within(privatePanel).getByRole('button', { name: 'Carol' }));
    await userEvent.type(screen.getByLabelText('Message'), 'Ping');
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }));

    expect(send).toHaveBeenCalledWith({ type: 'private_message', target: 'Carol', text: 'Ping' });
  });
});
