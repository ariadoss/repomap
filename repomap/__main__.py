"""CLI entry point for repomap."""

import argparse
import subprocess
import sys
from pathlib import Path


_VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"

# PyPI package versions — primary install source
_TS_VERSION = "0.21.3"
_TSL_VERSION = "1.10.2"

# GitHub release fallback — used when PyPI is unavailable
_TSL_GITHUB_REPO = "grantjenks/py-tree-sitter-languages"
_TSL_GITHUB_TAG = "v1.10.2"


def _ensure_dependency():
    """Install tree-sitter-languages, with multi-level fallback.

    Priority:
      1. Already installed (import succeeds) — done.
      2. pip install from PyPI with pinned versions.
      3. pip install from GitHub release tarball.
      4. Vendored copy in <repo>/vendor/ (user-managed).
    """
    # 1. Already installed?
    try:
        import tree_sitter_languages  # noqa: F401
        return
    except ImportError:
        pass

    # 2. Try PyPI
    print("Installing tree-sitter-languages from PyPI...", file=sys.stderr)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install",
             f"tree-sitter=={_TS_VERSION}",
             f"tree-sitter-languages=={_TSL_VERSION}",
             "--quiet"],
            stderr=subprocess.DEVNULL,
        )
        import tree_sitter_languages  # noqa: F401, F811
        return
    except (subprocess.CalledProcessError, ImportError):
        pass

    # 3. Try GitHub release
    print("PyPI unavailable, trying GitHub release...", file=sys.stderr)
    github_url = (
        f"https://github.com/{_TSL_GITHUB_REPO}/archive/refs/tags/"
        f"{_TSL_GITHUB_TAG}.tar.gz"
    )
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install",
             f"tree-sitter=={_TS_VERSION}",
             github_url,
             "--quiet"],
            stderr=subprocess.DEVNULL,
        )
        import tree_sitter_languages  # noqa: F401, F811
        return
    except (subprocess.CalledProcessError, ImportError):
        pass

    # 4. Try vendored copy
    if _VENDOR_DIR.is_dir():
        print("Using vendored tree-sitter-languages...", file=sys.stderr)
        sys.path.insert(0, str(_VENDOR_DIR))
        try:
            import tree_sitter_languages  # noqa: F401, F811
            return
        except ImportError:
            sys.path.pop(0)

    print(
        "Error: Could not install tree-sitter-languages.\n"
        "Install manually: pip install tree-sitter==0.21.3 "
        "tree-sitter-languages==1.10.2\n"
        "Or place a vendored copy in: " + str(_VENDOR_DIR),
        file=sys.stderr,
    )
    sys.exit(1)


_ensure_dependency()

from .mapper import generate_repo_map, update_file_in_map  # noqa: E402


def main():
    parser = argparse.ArgumentParser(
        description="Generate a structural codebase map using tree-sitter."
    )
    parser.add_argument(
        "repo",
        nargs="?",
        default=".",
        help="Path to the git repository (default: current directory)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        help="Maximum number of files to include",
    )
    parser.add_argument(
        "--update-file",
        help="Incrementally update a single file in an existing map",
    )
    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()
    if not (repo_path / ".git").exists():
        print(f"Error: {repo_path} is not a git repository.", file=sys.stderr)
        sys.exit(1)

    # Incremental update mode
    if args.update_file:
        map_file = Path(args.output) if args.output else repo_path / "REPOMAP.md"
        changed = update_file_in_map(repo_path, args.update_file, map_file)
        if changed:
            print(f"Updated {args.update_file} in {map_file}", file=sys.stderr)
        sys.exit(0)

    # Full generation mode
    result = generate_repo_map(repo_path, max_files=args.max_files)

    if not result.strip():
        print(
            "Warning: No definitions found. The project may use unsupported languages.",
            file=sys.stderr,
        )
        sys.exit(0)

    if args.output:
        Path(args.output).write_text(result)
        print(f"Repo map written to {args.output}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
