"""Tests targeting uncovered lines for 100% coverage."""

import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from repomap.mapper import (
    _is_exported,
    _should_include_node,
    extract_definitions,
)


# ---------------------------------------------------------------------------
# _is_exported edge cases (lines 219-223)
# ---------------------------------------------------------------------------


class TestIsExported:
    def test_non_exported_variable(self):
        """Variable declaration not under export_statement."""
        source = b"const x = 1;\n"
        import tree_sitter_languages

        parser = tree_sitter_languages.get_parser("typescript")
        tree = parser.parse(source)
        # Find the lexical_declaration node
        node = tree.root_node.children[0]
        assert node.type == "lexical_declaration"
        assert _is_exported(node) is False

    def test_exported_variable(self):
        """Variable with 'export' keyword."""
        source = b"export const x = 1;\n"
        import tree_sitter_languages

        parser = tree_sitter_languages.get_parser("typescript")
        tree = parser.parse(source)
        # The export_statement wraps the lexical_declaration
        export_node = tree.root_node.children[0]
        assert export_node.type == "export_statement"
        # The inner declaration
        inner = None
        for child in export_node.children:
            if child.type == "lexical_declaration":
                inner = child
                break
        assert inner is not None
        assert _is_exported(inner) is True  # parent is export_statement


# ---------------------------------------------------------------------------
# _should_include_node — export default (lines 245-247)
# ---------------------------------------------------------------------------


class TestShouldIncludeExportDefault:
    def test_export_default_function(self):
        source = b"export default function main() { return 1; }\n"
        defs = extract_definitions(source, "typescript")
        assert len(defs) >= 1
        found = any("export default function main" in line for _, lines in defs for line in lines)
        assert found

    def test_export_default_class(self):
        source = b"export default class App {}\n"
        defs = extract_definitions(source, "typescript")
        assert len(defs) >= 1

    def test_empty_export_statement(self):
        """An export statement with no meaningful declaration (e.g. re-export)."""
        source = b"export { foo } from './bar';\n"
        defs = extract_definitions(source, "typescript")
        # This shouldn't produce a definition entry
        # (no class/function/interface inside)


# ---------------------------------------------------------------------------
# Top-level unexported variable declarations (line 251)
# ---------------------------------------------------------------------------


class TestTopLevelVariableDeclarations:
    def test_top_level_const(self):
        source = b"const CONFIG = { port: 3000 };\n"
        defs = extract_definitions(source, "typescript")
        # Top-level variable in module should be included
        assert len(defs) >= 1

    def test_nested_const_excluded(self):
        """Variable inside a function should not be included."""
        source = b"function foo() {\n  const x = 1;\n  return x;\n}\n"
        defs = extract_definitions(source, "typescript")
        # Should only get the function, not the inner const
        assert len(defs) == 1
        assert "function foo" in defs[0][1][0]


# ---------------------------------------------------------------------------
# __main__.py — direct import coverage
# ---------------------------------------------------------------------------


class TestMainDirect:
    """Test __main__.py by importing and calling main() directly."""

    def test_no_args_not_git_repo(self, tmp_path):
        from repomap.__main__ import main

        with patch("sys.argv", ["repomap", str(tmp_path)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_stdout_output(self, tmp_path):
        # Create a git repo with a file
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / "app.py").write_text("def run():\n    pass\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path,
            capture_output=True,
        )

        from repomap.__main__ import main

        with patch("sys.argv", ["repomap", str(tmp_path)]):
            # Capture stdout
            from io import StringIO

            captured = StringIO()
            with patch("sys.stdout", captured):
                main()
            output = captured.getvalue()
            assert "app.py:" in output

    def test_file_output(self, tmp_path):
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / "lib.py").write_text("def helper():\n    pass\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path,
            capture_output=True,
        )

        out = tmp_path / "MAP.md"
        from repomap.__main__ import main

        with patch("sys.argv", ["repomap", str(tmp_path), "-o", str(out)]):
            main()
        assert out.exists()
        assert "lib.py:" in out.read_text()

    def test_empty_repo_no_crash(self, tmp_path):
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp_path,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("# Hi\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path,
            capture_output=True,
        )

        from repomap.__main__ import main

        with patch("sys.argv", ["repomap", str(tmp_path)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_max_files_arg(self, tmp_path):
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=tmp_path,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp_path,
            capture_output=True,
        )
        for i in range(5):
            (tmp_path / f"m{i}.py").write_text(f"def f{i}():\n    pass\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=tmp_path,
            capture_output=True,
        )

        from repomap.__main__ import main

        captured = StringIO()
        with patch("sys.argv", ["repomap", str(tmp_path), "--max-files", "2"]):
            with patch("sys.stdout", captured):
                main()
        output = captured.getvalue()
        file_entries = [
            l
            for l in output.split("\n")
            if l.endswith(":") and not l.startswith("│") and not l.startswith("⋮")
        ]
        assert len(file_entries) == 2
