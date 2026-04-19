Generate a repo map for the current project.

First, verify this is a git repository. If not, let the user know.

Then run this command:

```bash
PYTHONPATH=/Users/danilosapad/claude-repomap-command python3.11 -m repomap -o REPOMAP.md
```

The tool will auto-install `tree-sitter-languages` if it's not already installed.

If the command fails because the repomap package isn't found, tell the user to clone it:

```bash
git clone https://github.com/ariadoss/repomap.git ~/claude-repomap-command
```

After the command completes:
- If REPOMAP.md has content, confirm success and summarize what was mapped. Then ask the user: "Want me to add a rule to CLAUDE.md so Claude automatically references this map in future sessions?" If yes:
  - Check whether CLAUDE.md at the project root already contains the marker `<!-- repomap-rule -->`. If it does, the rule is already present — skip and tell the user.
  - Otherwise, append the block below to CLAUDE.md (create the file if it doesn't exist). Leave a blank line before the block if appending to existing content.

    ```
    <!-- repomap-rule -->
    ## REPOMAP.md

    REPOMAP.md at the project root is a structural outline of the codebase (files, classes, functions, types). Read it when the task benefits from a map: broad exploration, "where does X live", cross-module refactors, onboarding to an unfamiliar area, or planning changes that touch multiple files. Skip it for narrow lookups where Grep or a known file path is faster — a single symbol search doesn't need the whole map.
    ```
  If no, just let them know they can read it manually anytime.
- If REPOMAP.md is empty (0 bytes or only whitespace), delete the empty file and let the user know that the project may use unsupported languages
- If the command errored, share the error output so the user can troubleshoot
