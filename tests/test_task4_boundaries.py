import ast
import unittest
from pathlib import Path


class Task4BoundaryTest(unittest.TestCase):
    def assert_no_task4_imports(self, relative_path: str) -> None:
        source_path = Path(__file__).parents[1] / relative_path
        tree = ast.parse(source_path.read_text())
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }

        self.assertFalse(
            {module for module in imported_modules if module.startswith("src.task4.")},
            f"{relative_path} should be self-contained.",
        )

    def test_client_script_is_self_contained(self) -> None:
        self.assert_no_task4_imports("src/task4/client3.py")

    def test_server_script_is_self_contained(self) -> None:
        self.assert_no_task4_imports("src/task4/server3.py")


if __name__ == "__main__":
    unittest.main()
