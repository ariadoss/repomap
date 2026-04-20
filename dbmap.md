Generate a database schema map for the current project.

First, locate the repomap install. Search in this order and use the first hit:

1. `$REPOMAP_HOME` (if set)
2. `$HOME/claude-repomap-command`
3. `$HOME/.claude-repomap-command`
4. `$HOME/.local/share/claude-repomap-command`

If none of those contain a `scripts/run.sh` file, tell the user to clone the repo:

```bash
git clone https://github.com/ariadoss/repomap.git ~/claude-repomap-command
```

Then scan the project for database connection configurations (replace `<REPOMAP_DIR>` with the path you found):

```bash
<REPOMAP_DIR>/scripts/run.sh dbmap --list
```

The helper auto-detects a Python interpreter >= 3.8 and falls back to `uv`/`pyenv`/`asdf` if no compatible Python is on PATH.

This will detect database connections from .env files, Prisma schemas, Django settings, Rails database.yml, Knex configs, Sequelize configs, TypeORM configs, SQLAlchemy, Frappe site_config.json, Go config files, and docker-compose.yml.

Show the user the detected connections (with masked passwords). Ask which one to connect to. If no connections are found, ask the user for a DSN manually.

Once the user confirms a connection, run:

```bash
<REPOMAP_DIR>/scripts/run.sh dbmap --dsn '<confirmed_dsn>' -o DBMAP.md
```

Replace `<confirmed_dsn>` with the actual DSN string from the detected config (unmasked).

If tbls is not installed, the tool will attempt to install it via Homebrew or `go install`. If both fail, tell the user to install it manually: `brew install k1LoW/tap/tbls`

After the command completes:
- If DBMAP.md has content, confirm success and summarize the tables found. Then ask the user: "Want me to add a rule to CLAUDE.md so Claude automatically references this schema map in future sessions?" If yes:
  - Check whether CLAUDE.md at the project root already contains the marker `<!-- dbmap-rule -->`. If it does, the rule is already present — skip and tell the user.
  - Otherwise, append the block below to CLAUDE.md (create the file if it doesn't exist). Leave a blank line before the block if appending to existing content.

    ```
    <!-- dbmap-rule -->
    ## DBMAP.md

    DBMAP.md at the project root is the database schema map (tables, columns, types, constraints, relationships). Read it when the task involves the database: writing or reviewing queries, designing migrations, adding models or ORM mappings, debugging schema-related errors, or reasoning about joins and foreign keys. Skip it for pure application logic that doesn't touch the DB.
    ```
- If the command failed with a connection error, help the user troubleshoot (wrong host? DB not running? credentials?)
- If the command errored for another reason, share the error output
