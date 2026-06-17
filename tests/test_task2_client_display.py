import ast
import unittest
from pathlib import Path


class Task2ClientDisplayTest(unittest.TestCase):
    def test_client_does_not_use_builtin_print(self) -> None:
        source_path = Path(__file__).parents[1] / "src" / "task2" / "client1.py"
        tree = ast.parse(source_path.read_text())
        print_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ]

        self.assertEqual(print_calls, [])

    def test_client_logger_style_matches_server(self) -> None:
        root = Path(__file__).parents[1]
        client_source = (root / "src" / "task2" / "client1.py").read_text()
        server_source = (root / "src" / "task2" / "server1.py").read_text()

        expected_sink = 'lambda msg: console.print(msg, end="")'
        self.assertIn(expected_sink, server_source)
        self.assertIn(expected_sink, client_source)
        self.assertNotIn("logger.opt(raw=True)", client_source)
        self.assertNotIn("def log_chat_message", client_source)
        self.assertNotIn("def format_incoming_message", client_source)


if __name__ == "__main__":
    unittest.main()
