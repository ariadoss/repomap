# ⚠️ DEPRECATED (2026-10-07)

This repo is deprecated and archived. Reasoning, in full:

**The measurements.** Five pre-registered, eval-gated experiments
(synthetic fixtures + real production repos; full reports in
[superskills evals/reports](https://github.com/ariadoss/superskills/tree/main/evals/reports),
2026-10-06/07) found **no agent-context utility for these maps when
handed to tool-using agents**: agents given REPOMAP.md or DBMAP.md
performed the same or worse than agents that searched directly
(`grep`/read), and invoking the skill first cost 1.3–2x the turns. This
held on fresh maps, on a real 1,146-file monorepo, and even with the
team's own committed map sitting in the repo.

**The reconciliation with the idea's lineage.** Aider's repo map helps
because Aider's model has *no search tools* — the map is its grep — and
because Aider ships *ranked per-conversation slices*, not a static file.
Retrieval-time context engines rank per query. A static, broadcast map
in a tool-rich agent is the degenerate form of a good idea.

**What survived, and where it went.** dbmap's remaining real job — a
**fresh, provenance-stamped ground-truth artifact for work without live
database access** — moved to its own home:
[ariadoss/dbmap](https://github.com/ariadoss/dbmap). The `/dbmap` skill
lives on in [superskills](https://github.com/ariadoss/superskills) ≥
2.40.0 pointed at the new repo.

**repomap-the-tool** (tree-sitter code outlines) remains functional in
this archived repo for humans and pipelines — clones still work — but it
is unmaintained, and its pinned dependency stack
(`tree-sitter-languages` 1.10.2, cp311-only wheels) is aging. Known bug
frozen as-is: `scripts/run.sh`'s interpreter probe picks any python ≥ 3.8
without checking whether the pinned deps import, which breaks on hosts
defaulting to python3.13 (patch exists in the wild; not landing here).
Existing clones — including user-level auto-update hooks — are
unaffected by archiving.

Unarchiving is possible if ever needed.

---

# repomap + dbmap — Code & Database Maps for AI Coding Tools

Two tools that give AI coding agents complete project awareness:

- **repomap** — Generates a structural map of your codebase using [tree-sitter](https://tree-sitter.github.io/tree-sitter/). No LLM API calls, no tokens burned — pure local parsing, instant results. Saved as `REPOMAP.md`.
- **dbmap** — Generates a database schema map using [tbls](https://github.com/k1LoW/tbls). Auto-detects database connections from your project config files with a confirmation step before connecting. Saved as `DBMAP.md`.

## Measured note (2026-10): what these are good for now

Five pre-registered, eval-gated experiments (synthetic fixtures + real
repos, reports:
[superskills evals](https://github.com/ariadoss/superskills/tree/main/evals/reports))
measured **no agent-context utility for these maps when handed to
tool-using agents** (Claude-class models with Grep/Glob/Read): agents
given a map performed the same or worse than agents that searched
directly, and invoking the skill first cost 1.3–2x the turns. That is a
statement about *this deployment* — static, broadcast maps competing
with targeted search. The idea's lineage (Aider's per-conversation ranked
repo map; retrieval-time context engines) works where the model cannot
search, or where retrieval is ranked per query; a static file is the
degenerate form.

**Where dbmap still earns its keep:** as a *ground-truth artifact* for
work without live database access — committed, kept fresh (see the auto
toggles), and pointed at by a repo rule. Two improvements follow from the
measurements: stamp DBMAP.md's header with generation time and source
database (provenance was the gap agents flagged), and treat it as the
record of the deployed schema, not as agent context.

repomap remains available here as a standalone tool for humans and
pipelines; it was removed from the superskills plugin in v2.39.0.

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

Clone to any location — the default is `~/claude-repomap-command`, but `~/.claude-repomap-command`, `~/.local/share/claude-repomap-command`, or a custom path set via `$REPOMAP_HOME` all work:

```bash
git clone https://github.com/ariadoss/repomap.git ~/claude-repomap-command
```

Invoke via `scripts/run.sh`, which auto-detects a compatible Python and sets `PYTHONPATH` for you:

```bash
~/claude-repomap-command/scripts/run.sh repomap -o REPOMAP.md
~/claude-repomap-command/scripts/run.sh dbmap --list
```

Python is detected in this order: `python3.13` → `python3.12` → … → `python3.8` → `python3` → `python`. The first binary on `PATH` that reports `>= 3.8` is used. If none qualify, the helper falls back to `uv`, then `pyenv`, then `asdf` to provision Python 3.11. It errors with install links only if all four strategies fail.

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
cp dbmap-auto-on.md ~/.claude/commands/dbmap-auto-on.md
cp dbmap-auto-off.md ~/.claude/commands/dbmap-auto-off.md

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

After generating, the command optionally appends a rule block to `CLAUDE.md` (creating it if needed) so Claude automatically references the map in future sessions. The rule is conditional — it tells Claude to consult `REPOMAP.md` for broad exploration, cross-module refactors, and "where does X live" questions, and to skip it for narrow single-symbol lookups where Grep is cheaper. A `<!-- repomap-rule -->` marker makes the step idempotent (re-running won't duplicate the rule). The equivalent `/dbmap` step appends a `<!-- dbmap-rule -->` block for the schema map.

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

### Auto-update on migrations

Keep `DBMAP.md` in sync with the live schema by enabling auto-updates:

```
/dbmap-auto-on    # asks for a DSN, writes it to .dbmap-auto, gitignores it
/dbmap-auto-off   # disables
```

When enabled, a Claude Code PostToolUse hook fires on `Bash` calls and regenerates `DBMAP.md` whenever it sees a migration command run (Rails `db:migrate`, Django `manage.py migrate`, Alembic `upgrade`, `prisma migrate`/`prisma db push`, `knex migrate`, `sequelize db:migrate`, `goose up`, `dbmate up/migrate`, `flyway migrate`, `liquibase update`, `typeorm migration:run`, `drizzle-kit migrate/push`).

The hook is gated on three things being true: `.dbmap-auto` exists, `DBMAP.md` exists, and the bash command matches the migration regex. It only re-queries the DB after the schema has actually changed — editing a migration file does not trigger it.

**Security:** `.dbmap-auto` contains a database DSN with credentials. `/dbmap-auto-on` adds it to `.gitignore` automatically; never commit it.

Add this to `~/.claude/settings.json` once (the slash commands won't add it for you):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "if [ -f .dbmap-auto ] && [ -f DBMAP.md ]; then CMD=$(jq -r '.tool_input.command // empty'); if echo \"$CMD\" | grep -qE '(db:migrate|manage\\.py migrate|alembic upgrade|prisma (migrate|db push)|knex migrate|sequelize db:migrate|goose up|dbmate (up|migrate)|flyway migrate|liquibase update|typeorm migration:run|drizzle-kit (migrate|push))'; then DSN=$(head -n1 .dbmap-auto); [ -n \"$DSN\" ] && \"${REPOMAP_HOME:-$HOME/claude-repomap-command}/scripts/run.sh\" dbmap --dsn \"$DSN\" -o DBMAP.md 2>/dev/null; fi; fi",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

If you also have the repomap auto-update hook configured, add this as a second entry in the `PostToolUse` array — they're independent (different matchers).

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

## License

MIT, see [LICENSE](LICENSE).
