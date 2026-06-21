import unittest

from src.task1 import client0
from src.task2 import client1
from src.task3 import client2
from src.task4 import client3


class ClientServerArgsTest(unittest.TestCase):
    def test_each_client_accepts_server_and_port_options(self) -> None:
        for module in (client0, client1, client2, client3):
            with self.subTest(module=module.__name__):
                args = module.parse_server_args(["--server", "192.168.1.1", "--port", "9001"])

                self.assertEqual(args.server, "192.168.1.1")
                self.assertEqual(args.port, 9001)


if __name__ == "__main__":
    unittest.main()
