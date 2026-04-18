"""CLI entry point for dbmap."""

import argparse
import sys
from pathlib import Path

from .detector import detect_all, mask_password
from .generator import generate_dbmap, format_dbmap, install_tbls


def main():
    parser = argparse.ArgumentParser(
        description="Generate a database schema map using tbls."
    )
    parser.add_argument(
        "repo",
        nargs="?",
        default=".",
        help="Path to the project (default: current directory)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="DBMAP.md",
        help="Output file path (default: DBMAP.md)",
    )
    parser.add_argument(
        "--dsn",
        help="Database connection string (skip auto-detection)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip interactive confirmation (for CI/scripts)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="List detected database connections and exit",
    )
    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()

    # If --dsn provided, skip detection
    if args.dsn:
        dsn = args.dsn
        source = "manual --dsn"
    else:
        # Detect database configs
        configs = detect_all(repo_path)

        if not configs:
            print(
                "No database configurations found.\n"
                "Use --dsn to provide a connection string manually:\n"
                "  python3 -m dbmap --dsn 'postgres://user:pass@localhost:5432/mydb'",
                file=sys.stderr,
            )
            sys.exit(1)

        # List mode
        if args.list_only:
            print(f"Found {len(configs)} database connection(s):\n")
            for i, cfg in enumerate(configs, 1):
                print(f"  [{i}] {cfg.source}")
                print(f"      DSN: {mask_password(cfg.dsn)}")
                print(f"      Type: {cfg.db_type}")
                if cfg.name:
                    print(f"      Database: {cfg.name}")
                print()
            sys.exit(0)

        # Show found configs and ask for confirmation
        print(f"Found {len(configs)} database connection(s):\n", file=sys.stderr)
        for i, cfg in enumerate(configs, 1):
            print(f"  [{i}] {cfg.source}", file=sys.stderr)
            print(f"      DSN: {mask_password(cfg.dsn)}", file=sys.stderr)
            print(f"      Type: {cfg.db_type}", file=sys.stderr)
            if cfg.name:
                print(f"      Database: {cfg.name}", file=sys.stderr)
            print(file=sys.stderr)

        if not args.confirm:
            # Interactive selection
            if len(configs) == 1:
                prompt = "Connect to this database? [y/N]: "
            else:
                prompt = f"Select a database [1-{len(configs)}] or 'n' to cancel: "

            try:
                choice = input(prompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled.", file=sys.stderr)
                sys.exit(0)

            if len(configs) == 1:
                if choice not in ("y", "yes"):
                    print("Cancelled.", file=sys.stderr)
                    sys.exit(0)
                selected = configs[0]
            else:
                if choice in ("n", "no", ""):
                    print("Cancelled.", file=sys.stderr)
                    sys.exit(0)
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(configs):
                        selected = configs[idx]
                    else:
                        print("Invalid selection.", file=sys.stderr)
                        sys.exit(1)
                except ValueError:
                    print("Invalid selection.", file=sys.stderr)
                    sys.exit(1)
        else:
            # --confirm: use first detected config
            selected = configs[0]

        dsn = selected.dsn
        source = selected.source

    # Ensure tbls is installed
    tbls_path = install_tbls()
    if not tbls_path:
        print(
            "Error: tbls is not installed and could not be auto-installed.\n"
            "Install manually:\n"
            "  brew install k1LoW/tap/tbls\n"
            "  or: go install github.com/k1LoW/tbls@latest",
            file=sys.stderr,
        )
        sys.exit(1)

    # Generate the schema map
    print(f"Connecting to database...", file=sys.stderr)
    try:
        content = generate_dbmap(dsn, tbls_path=tbls_path)
    except ConnectionError as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not content:
        print("Warning: No schema data returned.", file=sys.stderr)
        sys.exit(0)

    output = format_dbmap(content, dsn_source=source)
    output_path = Path(args.output)
    output_path.write_text(output)
    print(f"Database schema map written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
