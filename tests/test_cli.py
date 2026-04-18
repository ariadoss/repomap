"""Tests for the CLI entry point (__main__.py)."""

import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(args, cwd=None):
    """Run repomap CLI and return result."""
    return subprocess.run(
        [sys.executable, "-m", "repomap"] + args,
        capture_output=True,
        text=True,
        cwd=cwd or Path(__file__).parent.parent,
    )


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


class TestCLI:
    def test_not_a_git_repo(self, tmp_path):
        result = _run_cli([str(tmp_path)])
        assert result.returncode == 1
        assert "not a git repository" in result.stderr

    def test_stdout_output(self, git_repo):
        _add_and_commit(git_repo, {"app.py": "def main():\n    pass\n"})
        result = _run_cli([str(git_repo)])
        assert result.returncode == 0
        assert "app.py:" in result.stdout
        assert "│def main():" in result.stdout

    def test_file_output(self, git_repo):
        _add_and_commit(git_repo, {"app.py": "def main():\n    pass\n"})
        out_file = git_repo / "REPOMAP.md"
        result = _run_cli([str(git_repo), "-o", str(out_file)])
        assert result.returncode == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "app.py:" in content

    def test_max_files(self, git_repo):
        files = {f"f{i}.py": f"def fn{i}():\n    pass\n" for i in range(10)}
        _add_and_commit(git_repo, files)
        result = _run_cli([str(git_repo), "--max-files", "3"])
        assert result.returncode == 0
        file_entries = [
            l for l in result.stdout.split("\n") if l.endswith(":") and not l.startswith("│") and not l.startswith("⋮")
        ]
        assert len(file_entries) == 3

    def test_empty_repo_warning(self, git_repo):
        _add_and_commit(git_repo, {"README.md": "# Hi\n"})
        result = _run_cli([str(git_repo)])
        assert result.returncode == 0
        assert "No definitions found" in result.stderr

    def test_default_cwd(self, git_repo):
        _add_and_commit(git_repo, {"lib.py": "def lib():\n    pass\n"})
        result = subprocess.run(
            [sys.executable, "-m", "repomap"],
            capture_output=True,
            text=True,
            cwd=git_repo,
            env={**subprocess.os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)},
        )
        assert result.returncode == 0
        assert "lib.py:" in result.stdout
