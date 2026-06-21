import unittest

from src.task4.server3 import ChatServerState, FileTransfer, SocketReader


class FakeSocket:
    def __init__(self) -> None:
        self.messages: list[bytes] = []

    def sendall(self, data: bytes) -> None:
        self.messages.append(data)

    @property
    def text_messages(self) -> list[str]:
        return [message.decode("utf-8") for message in self.messages]


class ChunkedSocket:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    def recv(self, size: int) -> bytes:
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if len(chunk) <= size:
            return chunk
        self.chunks.insert(0, chunk[size:])
        return chunk[:size]


class Task4ServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = ChatServerState()
        self.alice = FakeSocket()
        self.bob = FakeSocket()
        self.carol = FakeSocket()
        self.state.add_client(self.alice, "alice")
        self.state.add_client(self.bob, "bob")
        self.state.add_client(self.carol, "carol")

    def test_task3_commands_still_work(self) -> None:
        self.state.handle_command(self.alice, "/create study")
        self.state.handle_command(self.bob, "/join study")
        self.state.handle_command(self.alice, "/room hello room")
        self.state.handle_command(self.alice, "/pm carol private hello")

        self.assertIn("[ROOM study | alice] hello room\n", self.bob.text_messages)
        self.assertIn("[PM from alice] private hello\n", self.carol.text_messages)

    def test_new_clients_can_send_to_default_general_room(self) -> None:
        self.state.handle_command(self.alice, "/room hello general")

        self.assertIn("[ROOM general | alice] hello general\n", self.bob.text_messages)
        self.assertIn("[ROOM general | alice] hello general\n", self.carol.text_messages)

    def test_user_list_is_pushed_when_clients_change(self) -> None:
        state = ChatServerState()
        alice = FakeSocket()
        bob = FakeSocket()

        state.add_client(alice, "alice")
        state.add_client(bob, "bob")
        state.remove_client(bob)

        self.assertIn("[SERVER] Online users: alice\n", alice.text_messages)
        self.assertIn("[SERVER] Online users: alice, bob\n", alice.text_messages)
        self.assertIn("[SERVER] Online users: alice, bob\n", bob.text_messages)
        self.assertEqual(alice.text_messages[-1], "[SERVER] Online users: alice\n")

    def test_room_list_is_pushed_when_rooms_change(self) -> None:
        state = ChatServerState()
        alice = FakeSocket()
        bob = FakeSocket()

        state.add_client(alice, "alice")
        state.add_client(bob, "bob")
        state.handle_command(alice, "/create study")
        state.handle_command(bob, "/join study")
        state.handle_command(alice, "/leave")

        self.assertIn("[SERVER] Rooms: general, study\n", alice.text_messages)
        self.assertIn("[SERVER] Rooms: general, study\n", bob.text_messages)
        self.assertNotIn("[SERVER] Rooms: study\n", alice.text_messages)

    def test_created_rooms_stay_listed_after_creator_creates_another_room(self) -> None:
        state = ChatServerState()
        alice = FakeSocket()
        state.add_client(alice, "alice")

        state.handle_command(alice, "/create study")
        state.handle_command(alice, "/create lab")

        self.assertEqual(state.rooms_message(), "[SERVER] Rooms: general, lab, study\n")
        self.assertIn("[SERVER] Rooms: general, study\n", alice.text_messages)
        self.assertIn("[SERVER] Rooms: general, lab, study\n", alice.text_messages)

    def test_created_room_stays_listed_after_switching_to_general(self) -> None:
        state = ChatServerState()
        alice = FakeSocket()
        state.add_client(alice, "alice")

        state.handle_command(alice, "/create new-room")
        state.handle_command(alice, "/join general")

        self.assertEqual(state.rooms_message(), "[SERVER] Rooms: general, new-room\n")

    def test_delete_room_removes_room_and_moves_members_to_general(self) -> None:
        state = ChatServerState()
        alice = FakeSocket()
        bob = FakeSocket()
        state.add_client(alice, "alice")
        state.add_client(bob, "bob")

        state.handle_command(alice, "/create study")
        state.handle_command(bob, "/join study")
        state.handle_command(alice, "/delete study")

        self.assertEqual(state.rooms_message(), "[SERVER] Rooms: general\n")
        self.assertEqual(state.client_rooms[alice], "general")
        self.assertEqual(state.client_rooms[bob], "general")
        self.assertIn("[SERVER] Deleted room: study\n", alice.text_messages)

    def test_file_transfer_header_round_trips(self) -> None:
        transfer = FileTransfer(
            filename="notes.txt",
            size=11,
            mime_type="text/plain",
            sender="alice",
            scope="room",
            target="study",
        )

        parsed = FileTransfer.from_header(transfer.to_header())

        self.assertEqual(parsed, transfer)

    def test_room_file_transfer_routes_only_to_room_members(self) -> None:
        self.state.handle_command(self.alice, "/create study")
        self.state.handle_command(self.bob, "/join study")
        payload = b"hello file"
        transfer = FileTransfer(
            filename="notes.txt",
            size=len(payload),
            mime_type="text/plain",
            sender="alice",
            scope="room",
            target="study",
        )

        self.state.route_file_transfer(self.alice, transfer, payload)

        self.assertIn(payload, self.bob.messages)
        self.assertNotIn(payload, self.carol.messages)
        self.assertTrue(any("[FILE from alice]" in message for message in self.bob.text_messages))

    def test_socket_reader_preserves_payload_when_header_and_bytes_arrive_together(self) -> None:
        payload = b"abc123"
        transfer = FileTransfer(
            filename="notes.txt",
            size=len(payload),
            mime_type="text/plain",
            sender="alice",
            scope="public",
            target="",
        )
        reader = SocketReader(ChunkedSocket([(transfer.to_header()).encode("utf-8") + payload]))

        self.assertEqual(reader.recv_line(), transfer.to_header().strip())
        self.assertEqual(reader.recv_exact(len(payload)), payload)


if __name__ == "__main__":
    unittest.main()
