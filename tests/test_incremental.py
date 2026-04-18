"""Tests for incremental repo map updates."""

import subprocess
from pathlib import Path

import pytest

from repomap.mapper import _parse_repo_map, update_file_in_map


@pytest.fixture
def git_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
    )
    return tmp_path


def _add_and_commit(repo, files):
    for path, content in files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add"], cwd=repo, capture_output=True
    )


class TestParseRepoMap:
    def test_single_file(self):
        content = "app.py:\n⋮\n│def main():\n⋮\n"
        entries = _parse_repo_map(content)
        assert "app.py" in entries
        assert "│def main():" in entries["app.py"]

    def test_multiple_files(self):
        content = (
            "a.py:\n⋮\n│def a():\n⋮\n\n"
            "b.py:\n⋮\n│def b():\n⋮\n"
        )
        entries = _parse_repo_map(content)
        assert len(entries) == 2
        assert "a.py" in entries
        assert "b.py" in entries

    def test_empty_content(self):
        entries = _parse_repo_map("")
        assert entries == {}

    def test_preserves_entry_content(self):
        content = "lib.py:\n⋮\n│class Foo:\n│  pass\n⋮\n│def bar():\n⋮\n"
        entries = _parse_repo_map(content)
        assert "│class Foo:" in entries["lib.py"]
        assert "│def bar():" in entries["lib.py"]


class TestUpdateFileInMap:
    def test_creates_map_when_none_exists(self, git_repo):
        _add_and_commit(git_repo, {"app.py": "def main():\n    pass\n"})
        map_path = git_repo / "REPOMAP.md"
        assert not map_path.exists()

        changed = update_file_in_map(git_repo, "app.py", map_path)
        assert changed is True
        assert map_path.exists()
        assert "app.py:" in map_path.read_text()

    def test_adds_new_file_to_existing_map(self, git_repo):
        _add_and_commit(
            git_repo,
            {
                "a.py": "def a():\n    pass\n",
                "b.py": "def b():\n    pass\n",
            },
        )
        map_path = git_repo / "REPOMAP.md"

        # Create initial map with just a.py
        from repomap.mapper import generate_repo_map

        map_path.write_text(generate_repo_map(git_repo, max_files=1))
        assert "a.py:" in map_path.read_text()
        assert "b.py:" not in map_path.read_text()

        # Incrementally add b.py
        changed = update_file_in_map(git_repo, "b.py", map_path)
        assert changed is True
        content = map_path.read_text()
        assert "a.py:" in content
        assert "b.py:" in content

    def test_updates_modified_file(self, git_repo):
        _add_and_commit(git_repo, {"app.py": "def old_func():\n    pass\n"})
        map_path = git_repo / "REPOMAP.md"

        from repomap.mapper import generate_repo_map

        map_path.write_text(generate_repo_map(git_repo))
        assert "old_func" in map_path.read_text()

        # Modify the file
        (git_repo / "app.py").write_text("def new_func():\n    pass\n")

        changed = update_file_in_map(git_repo, "app.py", map_path)
        assert changed is True
        content = map_path.read_text()
        assert "new_func" in content
        assert "old_func" not in content

    def test_removes_deleted_file(self, git_repo):
        _add_and_commit(
            git_repo,
            {
                "a.py": "def a():\n    pass\n",
                "b.py": "def b():\n    pass\n",
            },
        )
        map_path = git_repo / "REPOMAP.md"

        from repomap.mapper import generate_repo_map

        map_path.write_text(generate_repo_map(git_repo))
        assert "b.py:" in map_path.read_text()

        # Delete b.py
        (git_repo / "b.py").unlink()

        changed = update_file_in_map(git_repo, "b.py", map_path)
        assert changed is True
        content = map_path.read_text()
        assert "a.py:" in content
        assert "b.py:" not in content

    def test_no_change_returns_false(self, git_repo):
        _add_and_commit(git_repo, {"app.py": "def main():\n    pass\n"})
        map_path = git_repo / "REPOMAP.md"

        from repomap.mapper import generate_repo_map

        map_path.write_text(generate_repo_map(git_repo))

        # Update with no changes
        changed = update_file_in_map(git_repo, "app.py", map_path)
        assert changed is False

    def test_unsupported_file_no_change(self, git_repo):
        _add_and_commit(
            git_repo,
            {
                "app.py": "def main():\n    pass\n",
                "readme.md": "# Hello\n",
            },
        )
        map_path = git_repo / "REPOMAP.md"

        from repomap.mapper import generate_repo_map

        map_path.write_text(generate_repo_map(git_repo))

        changed = update_file_in_map(git_repo, "readme.md", map_path)
        assert changed is False

    def test_file_emptied_removes_entry(self, git_repo):
        _add_and_commit(git_repo, {"app.py": "def main():\n    pass\n"})
        map_path = git_repo / "REPOMAP.md"

        from repomap.mapper import generate_repo_map

        map_path.write_text(generate_repo_map(git_repo))
        assert "app.py:" in map_path.read_text()

        # Empty the file
        (git_repo / "app.py").write_text("")

        changed = update_file_in_map(git_repo, "app.py", map_path)
        assert changed is True
        assert "app.py:" not in map_path.read_text()

    def test_maintains_sorted_order(self, git_repo):
        _add_and_commit(
            git_repo,
            {
                "a.py": "def a():\n    pass\n",
                "c.py": "def c():\n    pass\n",
            },
        )
        map_path = git_repo / "REPOMAP.md"

        from repomap.mapper import generate_repo_map

        map_path.write_text(generate_repo_map(git_repo))

        # Add b.py which should sort between a and c
        (git_repo / "b.py").write_text("def b():\n    pass\n")
        subprocess.run(["git", "add", "b.py"], cwd=git_repo, capture_output=True)

        changed = update_file_in_map(git_repo, "b.py", map_path)
        assert changed is True
        content = map_path.read_text()
        a_pos = content.index("a.py:")
        b_pos = content.index("b.py:")
        c_pos = content.index("c.py:")
        assert a_pos < b_pos < c_pos


class TestUpdateFileCLI:
    def test_incremental_via_cli(self, git_repo):
        import sys

        _add_and_commit(git_repo, {"app.py": "def main():\n    pass\n"})
        map_path = git_repo / "REPOMAP.md"

        result = subprocess.run(
            [sys.executable, "-m", "repomap", str(git_repo), "-o", str(map_path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        assert map_path.exists()

        # Modify file
        (git_repo / "app.py").write_text(
            "def main():\n    pass\n\ndef helper():\n    pass\n"
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "repomap",
                str(git_repo),
                "--update-file",
                "app.py",
                "-o",
                str(map_path),
            ],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert result.returncode == 0
        assert "helper" in map_path.read_text()
