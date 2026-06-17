import unittest

from src.task3.server2 import ChatServerState


class FakeSocket:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def sendall(self, data: bytes) -> None:
        self.messages.append(data.decode("utf-8"))


class Task3ServerCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = ChatServerState()
        self.alice = FakeSocket()
        self.bob = FakeSocket()
        self.carol = FakeSocket()
        self.state.add_client(self.alice, "alice")
        self.state.add_client(self.bob, "bob")
        self.state.add_client(self.carol, "carol")

    def test_private_message_is_sent_only_to_target_and_sender(self) -> None:
        self.state.handle_command(self.alice, "/pm bob hello bob")

        self.assertEqual(self.bob.messages, ["[PM from alice] hello bob\n"])
        self.assertEqual(self.alice.messages, ["[PM to bob] hello bob\n"])
        self.assertEqual(self.carol.messages, [])

    def test_room_message_is_sent_only_to_room_members_except_sender(self) -> None:
        self.state.handle_command(self.alice, "/create study")
        self.state.handle_command(self.bob, "/join study")
        self.state.handle_command(self.alice, "/room tomorrow at nine")

        self.assertIn("[ROOM study | alice] tomorrow at nine\n", self.bob.messages)
        self.assertNotIn("[ROOM study | alice] tomorrow at nine\n", self.alice.messages)
        self.assertEqual(self.carol.messages, [])

    def test_leave_removes_client_from_room(self) -> None:
        self.state.handle_command(self.alice, "/create study")
        self.state.handle_command(self.bob, "/join study")
        self.state.handle_command(self.bob, "/leave")
        self.state.handle_command(self.alice, "/room after leave")

        self.assertNotIn("[ROOM study | alice] after leave\n", self.bob.messages)
        self.assertIsNone(self.state.client_rooms[self.bob])

    def test_changing_rooms_removes_client_from_previous_room(self) -> None:
        self.state.handle_command(self.alice, "/create study")
        self.state.handle_command(self.bob, "/join study")
        self.state.handle_command(self.bob, "/create games")
        self.state.handle_command(self.alice, "/room old room message")

        self.assertNotIn("[ROOM study | alice] old room message\n", self.bob.messages)
        self.assertEqual(self.state.client_rooms[self.bob], "games")

    def test_joining_current_room_keeps_membership(self) -> None:
        self.state.handle_command(self.alice, "/create study")
        self.state.handle_command(self.alice, "/join study")

        self.assertEqual(self.state.client_rooms[self.alice], "study")
        self.assertIn(self.alice, self.state.rooms["study"])

    def test_list_shows_online_users(self) -> None:
        self.state.handle_command(self.alice, "/list")

        self.assertEqual(self.alice.messages[-1], "[SERVER] Online users: alice, bob, carol\n")


if __name__ == "__main__":
    unittest.main()
