# repomap + dbmap — Code & Database Maps for AI Coding Tools

Two tools that give AI coding agents complete project awareness:

- **repomap** — Generates a structural map of your codebase using [tree-sitter](https://tree-sitter.github.io/tree-sitter/). No LLM API calls, no tokens burned — pure local parsing, instant results. Saved as `REPOMAP.md`.
- **dbmap** — Generates a database schema map using [tbls](https://github.com/k1LoW/tbls). Auto-detects database connections from your project config files with a confirmation step before connecting. Saved as `DBMAP.md`.

## How it works

Uses tree-sitter to parse your source files and extract definitions (classes, functions, interfaces, types, etc.) into a concise outline:

```
src/handler.ts:
⋮
│interface HandlerProps {
│  method: string;
⋮
│export function handle(props: HandlerProps) {
│  return props.method;
⋮
```

## Prerequisites

- Python 3.8+
- git (maps git-tracked files only)
- `tree-sitter-languages` (auto-installed on first run)

## Installation

```bash
git clone https://github.com/ariadoss/repomap.git ~/claude-repomap-command
```

Dependencies are automatically resolved on first run with this fallback chain:

1. **Already installed** — uses existing `tree-sitter-languages`
2. **PyPI** — `pip install` with pinned versions
3. **GitHub release** — installs directly from the `grantjenks/py-tree-sitter-languages` release tarball
4. **Vendored copy** — uses `vendor/` directory if present (for air-gapped/offline environments)

To install manually:

```bash
pip install -r requirements.txt
```

To create a vendored offline fallback (platform-specific):

```bash
./scripts/vendor-deps.sh
```

### Claude Code slash commands

```bash
# Global (all projects)
mkdir -p ~/.claude/commands
cp repomap.md ~/.claude/commands/repomap.md
cp repomap-auto-on.md ~/.claude/commands/repomap-auto-on.md
cp repomap-auto-off.md ~/.claude/commands/repomap-auto-off.md
cp dbmap.md ~/.claude/commands/dbmap.md

# Per-project
mkdir -p .claude/commands
cp repomap.md .claude/commands/repomap.md
cp dbmap.md .claude/commands/dbmap.md
```

## Usage

### Command line

```bash
# Full generation — map entire repo to stdout
python3 -m repomap /path/to/repo

# Full generation — write to file
python3 -m repomap /path/to/repo -o REPOMAP.md

# Full generation — limit number of files
python3 -m repomap /path/to/repo -o REPOMAP.md --max-files 50

# Incremental update — re-parse a single changed file in an existing map
python3 -m repomap /path/to/repo --update-file src/app.ts -o REPOMAP.md
```

### CLI reference

| Flag | Description |
|------|-------------|
| `repo` | Path to the git repository (default: current directory) |
| `-o`, `--output` | Output file path (default: stdout) |
| `--max-files N` | Maximum number of files to include in full generation |
| `--update-file PATH` | Incrementally update a single file in an existing map. Re-parses only the specified file and splices its entry into the map. If the file was deleted or has no definitions, its entry is removed. If no map exists yet, falls back to full generation. |

### Claude Code

**Generate a map:**

```
/repomap
```

After generating, the command optionally creates `.claude/rules/repomap.md` so Claude automatically references the map in future sessions.

**Enable auto-updates (updates map on every file edit):**

```
/repomap-auto-on
```

**Disable auto-updates:**

```
/repomap-auto-off
```

When auto-update is enabled, a `.repomap-auto` sentinel file is created in your project root. A Claude Code hook detects this file and runs an incremental update (~30ms) every time you edit a file. Delete `.repomap-auto` or run `/repomap-auto-off` to disable.

### OpenCode

Ask OpenCode to run the command, or reference `REPOMAP.md` in your project's `AGENTS.md`:

```markdown
See REPOMAP.md for a structural overview of the codebase.
```

## Auto-update hook setup (Claude Code)

The auto-update hook is configured in `~/.claude/settings.json`. If you installed the slash commands, just use `/repomap-auto-on` and `/repomap-auto-off`. For manual setup, add this to your settings:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "if [ -f .repomap-auto ] && [ -f REPOMAP.md ]; then FILE=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty'); if [ -n \"$FILE\" ]; then REL=$(python3 -c \"import os,sys; print(os.path.relpath(sys.argv[1]))\" \"$FILE\" 2>/dev/null); python3 -m repomap --update-file \"$REL\" -o REPOMAP.md 2>/dev/null; fi; fi",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

The hook only fires when both `.repomap-auto` and `REPOMAP.md` exist in the project root.

## Supported languages

40+ languages via [tree-sitter-languages](https://github.com/grantjenks/py-tree-sitter-languages):

| Language | Extensions |
|----------|-----------|
| Python | `.py`, `.pyi` |
| TypeScript | `.ts`, `.mts`, `.cts`, `.tsx` |
| JavaScript | `.js`, `.mjs`, `.cjs`, `.jsx` |
| Go | `.go` |
| Rust | `.rs` |
| Ruby | `.rb`, `.rake`, `.gemspec` |
| Java | `.java` |
| Kotlin | `.kt`, `.kts` |
| C# | `.cs` |
| C | `.c`, `.h` |
| C++ | `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hxx`, `.hh` |
| PHP | `.php` |
| Swift | `.swift` |
| Scala | `.scala` |
| Lua | `.lua` |
| R | `.r`, `.R` |
| Zig | `.zig` |
| Elixir | `.ex`, `.exs` |
| Erlang | `.erl`, `.hrl` |
| Haskell | `.hs` |
| OCaml | `.ml`, `.mli` |
| Dart | `.dart` |
| Perl | `.pl`, `.pm` |
| Julia | `.jl` |
| Elm | `.elm` |
| Fortran | `.f90`, `.f95`, `.f03`, `.f08`, `.f` |
| Objective-C | `.m`, `.mm` |
| Hack | `.hack` |
| Common Lisp | `.lisp`, `.cl`, `.lsp` |
| HCL/Terraform | `.hcl`, `.tf` |
| SQL | `.sql` |
| Vue | `.vue` |
| Shell | `.sh`, `.bash`, `.zsh` |
| Dockerfile | `Dockerfile` |
| Makefile | `Makefile` |

---

## /dbmap — Database Schema Map

Generate a database schema map by auto-detecting your project's database connection and running [tbls](https://github.com/k1LoW/tbls).

### How it works

1. Scans your project for database connection configs
2. Shows what it found (with masked passwords) and asks you to confirm
3. Connects to the database and generates schema documentation
4. Writes `DBMAP.md` with table listings, columns, types, constraints, and relationships

### Prerequisites

- [tbls](https://github.com/k1LoW/tbls) (auto-installed via Homebrew or `go install` on first run)
- A running database to connect to

### Command line

```bash
# Auto-detect and list database connections
python3 -m dbmap /path/to/project --list

# Auto-detect, confirm, and generate
python3 -m dbmap /path/to/project -o DBMAP.md

# Skip detection — provide DSN directly
python3 -m dbmap --dsn 'mysql://user:pass@localhost:3306/mydb' -o DBMAP.md

# Non-interactive (use first detected config)
python3 -m dbmap /path/to/project --confirm -o DBMAP.md
```

### CLI reference

| Flag | Description |
|------|-------------|
| `repo` | Path to the project (default: current directory) |
| `-o`, `--output` | Output file path (default: DBMAP.md) |
| `--dsn DSN` | Database connection string (skip auto-detection) |
| `--confirm` | Skip interactive confirmation, use first detected config |
| `--list` | List detected database connections and exit |

### Claude Code

```
/dbmap
```

The slash command scans your project, shows detected connections, and asks which to use before connecting.

### Supported config formats

Auto-detection scans for database connections in:

| Framework/Tool | Config files |
|---------------|-------------|
| Environment files | `.env`, `.env.local`, `.env.development` (root + subdirs) |
| Prisma | `schema.prisma` → `env("DATABASE_URL")` or direct URL |
| Django | `settings.py` → `DATABASES` dict |
| Rails | `config/database.yml` → development section |
| Laravel | `.env` → `DB_HOST`/`DB_DATABASE` vars |
| Knex | `knexfile.js/ts` → connection string or object |
| Sequelize | `config/config.json` → development section |
| TypeORM | `ormconfig.json/ts` → url or host/database |
| SQLAlchemy | `create_engine()` or `SQLALCHEMY_DATABASE_URI` in `.py` |
| Frappe | `site_config.json` → db_host/db_name |
| Go projects | `config.yaml` → database block, DSN strings in `.go` |
| Docker Compose | `docker-compose.yml` → MySQL/MariaDB/PostgreSQL services |
| WordPress | `wp-config.php` → `DB_NAME`/`DB_HOST` defines |
| Generic | `.cfg`/`.ini` files with `MUSER`/`MHOST` or `DB_USER`/`DB_HOST` |

### Security

- Passwords are **always masked** in display output (`****`)
- The tool **always asks for confirmation** before connecting (unless `--confirm` is passed)
- tbls only reads schema metadata — it never writes to the database
- Credentials are never written to `DBMAP.md`

## Running tests

```bash
pip install pytest pytest-cov
python3 -m pytest tests/ -v --cov=repomap --cov-report=term-missing
```

160 tests covering repomap (mapper.py 100%) and dbmap (all detectors).

## Tips

- Run `/repomap` once to generate the initial map, then `/repomap-auto-on` to keep it fresh
- Commit `REPOMAP.md` to your repo so teammates and other AI tools can benefit
- Use `--max-files` for large monorepos to keep the map focused
- Add `.repomap-auto` to `.gitignore` — it's a local preference, not a project setting
- Run `/dbmap` to add database schema context alongside your code map
- Commit both `REPOMAP.md` and `DBMAP.md` for full project awareness across tools
