"""Generate DBMAP.md using tbls."""

import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _find_tbls():
    """Find tbls binary, return path or None."""
    return shutil.which("tbls")


def install_tbls():
    """Attempt to install tbls. Returns path to binary or None."""
    existing = _find_tbls()
    if existing:
        return existing

    system = platform.system().lower()

    # Try brew (macOS/Linux)
    if shutil.which("brew"):
        print("Installing tbls via Homebrew...", file=sys.stderr)
        try:
            subprocess.check_call(
                ["brew", "install", "k1LoW/tap/tbls"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            path = _find_tbls()
            if path:
                return path
        except subprocess.CalledProcessError:
            pass

    # Try go install
    if shutil.which("go"):
        print("Installing tbls via go install...", file=sys.stderr)
        try:
            subprocess.check_call(
                ["go", "install", "github.com/k1LoW/tbls@latest"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Check GOPATH/bin
            gopath = os.environ.get("GOPATH", os.path.expanduser("~/go"))
            go_bin = os.path.join(gopath, "bin", "tbls")
            if os.path.isfile(go_bin):
                return go_bin
            path = _find_tbls()
            if path:
                return path
        except subprocess.CalledProcessError:
            pass

    return None


def _normalize_dsn_for_tbls(dsn):
    """Normalize a DSN for tbls compatibility.

    tbls expects specific DSN formats:
    - PostgreSQL: postgres://user:pass@host:port/db
    - MySQL: mysql://user:pass@host:port/db
    - SQLite: sqlite:///path/to/db
    """
    # MariaDB → MySQL (tbls uses mysql:// for both)
    if dsn.startswith("mariadb://"):
        dsn = "mysql://" + dsn[len("mariadb://"):]

    # postgresql:// → postgres:// (tbls prefers postgres://)
    if dsn.startswith("postgresql://"):
        dsn = "postgres://" + dsn[len("postgresql://"):]

    return dsn


def generate_dbmap(dsn, tbls_path=None, output_format="md"):
    """Run tbls and return the schema documentation as a string.

    Args:
        dsn: Database connection string.
        tbls_path: Path to tbls binary (auto-detected if None).
        output_format: Output format — "md" for markdown.

    Returns:
        Schema documentation as a string, or None on failure.

    Raises:
        RuntimeError: If tbls is not installed and can't be installed.
        ConnectionError: If the database connection fails.
    """
    if tbls_path is None:
        tbls_path = install_tbls()
    if tbls_path is None:
        raise RuntimeError(
            "tbls is not installed. Install it with:\n"
            "  brew install k1LoW/tap/tbls\n"
            "  or: go install github.com/k1LoW/tbls@latest"
        )

    dsn = _normalize_dsn_for_tbls(dsn)

    # Use a temp directory for tbls output
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [tbls_path, "doc", dsn, tmpdir],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            err_msg = stderr or stdout
            if "connection" in err_msg.lower() or "dial" in err_msg.lower():
                raise ConnectionError(
                    f"Could not connect to database: {err_msg}"
                )
            raise RuntimeError(f"tbls failed: {err_msg}")

        # Read the generated README.md (tbls creates this as the index)
        readme = Path(tmpdir) / "README.md"
        if not readme.is_file():
            return None

        output_parts = [readme.read_text()]

        # Also include individual table docs
        for table_doc in sorted(Path(tmpdir).glob("*.md")):
            if table_doc.name == "README.md":
                continue
            output_parts.append(f"\n---\n\n{table_doc.read_text()}")

        return "\n".join(output_parts)


def format_dbmap(content, dsn_source=""):
    """Wrap tbls output with a header for DBMAP.md."""
    header = "# Database Schema Map\n\n"
    if dsn_source:
        header += f"*Generated from: {dsn_source}*\n\n"
    return header + content
