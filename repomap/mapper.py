"""Core repo map generator using tree-sitter."""

import subprocess
from pathlib import Path

import tree_sitter_languages

# File extension → tree-sitter language name
EXT_TO_LANG = {
    # Python
    ".py": "python",
    ".pyi": "python",
    # JavaScript
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    # TypeScript
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # Ruby
    ".rb": "ruby",
    ".rake": "ruby",
    ".gemspec": "ruby",
    # Java
    ".java": "java",
    # Kotlin
    ".kt": "kotlin",
    ".kts": "kotlin",
    # C#
    ".cs": "c_sharp",
    # C
    ".c": "c",
    ".h": "c",
    # C++
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".hh": "cpp",
    # PHP
    ".php": "php",
    # Swift
    ".swift": "swift",
    # Scala
    ".scala": "scala",
    # Lua
    ".lua": "lua",
    # R
    ".r": "r",
    ".R": "r",
    # Zig
    ".zig": "zig",
    # Elixir
    ".ex": "elixir",
    ".exs": "elixir",
    # Erlang
    ".erl": "erlang",
    ".hrl": "erlang",
    # Haskell
    ".hs": "haskell",
    # OCaml
    ".ml": "ocaml",
    ".mli": "ocaml",
    # Dart
    ".dart": "dart",
    # Vue
    ".vue": "vue",
    # Shell
    ".bash": "bash",
    ".sh": "bash",
    ".zsh": "bash",
    # Perl
    ".pl": "perl",
    ".pm": "perl",
    # Julia
    ".jl": "julia",
    # Elm
    ".elm": "elm",
    # Fortran
    ".f90": "fortran",
    ".f95": "fortran",
    ".f03": "fortran",
    ".f08": "fortran",
    ".f": "fortran",
    # Objective-C
    ".m": "objc",
    ".mm": "objc",
    # Hack
    ".hack": "hack",
    ".hh": "hack",
    # HCL / Terraform
    ".hcl": "hcl",
    ".tf": "hcl",
    # SQL
    ".sql": "sql",
    # Dockerfile
    "Dockerfile": "dockerfile",
    # Makefile
    "Makefile": "make",
    "makefile": "make",
    # Common Lisp
    ".lisp": "commonlisp",
    ".cl": "commonlisp",
    ".lsp": "commonlisp",
    # Data formats (parsed but typically no definitions)
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".css": "css",
    ".scss": "css",
    ".html": "html",
    ".htm": "html",
}

# tree-sitter node types that represent definitions worth showing, per language.
DEFINITION_NODES = {
    "python": [
        "class_definition",
        "function_definition",
        "decorated_definition",
    ],
    "javascript": [
        "class_declaration",
        "function_declaration",
        "method_definition",
        "export_statement",
        "lexical_declaration",
        "variable_declaration",
    ],
    "typescript": [
        "class_declaration",
        "function_declaration",
        "method_definition",
        "interface_declaration",
        "type_alias_declaration",
        "enum_declaration",
        "export_statement",
        "lexical_declaration",
        "variable_declaration",
    ],
    "tsx": [
        "class_declaration",
        "function_declaration",
        "method_definition",
        "interface_declaration",
        "type_alias_declaration",
        "enum_declaration",
        "export_statement",
        "lexical_declaration",
        "variable_declaration",
    ],
    "go": [
        "function_declaration",
        "method_declaration",
        "type_declaration",
    ],
    "rust": [
        "function_item",
        "struct_item",
        "enum_item",
        "impl_item",
        "trait_item",
        "type_item",
        "mod_item",
    ],
    "ruby": [
        "class",
        "method",
        "module",
        "singleton_method",
    ],
    "java": [
        "class_declaration",
        "method_declaration",
        "interface_declaration",
        "enum_declaration",
        "constructor_declaration",
    ],
    "kotlin": [
        "class_declaration",
        "function_declaration",
        "object_declaration",
    ],
    "c_sharp": [
        "class_declaration",
        "method_declaration",
        "interface_declaration",
        "enum_declaration",
        "struct_declaration",
    ],
    "c": [
        "function_definition",
        "struct_specifier",
        "enum_specifier",
        "type_definition",
    ],
    "cpp": [
        "function_definition",
        "class_specifier",
        "struct_specifier",
        "enum_specifier",
        "template_declaration",
        "namespace_definition",
    ],
    "php": [
        "class_declaration",
        "function_definition",
        "method_declaration",
        "interface_declaration",
        "trait_declaration",
    ],
    "swift": [
        "class_declaration",
        "function_declaration",
        "protocol_declaration",
        "struct_declaration",
        "enum_declaration",
    ],
    "scala": [
        "class_definition",
        "function_definition",
        "object_definition",
        "trait_definition",
    ],
    "lua": [
        "function_declaration",
        "local_function_declaration_statement",
    ],
    "elixir": [
        "call",  # defmodule, def, defp
    ],
    "dart": [
        "class_declaration",
        "function_signature",
        "method_signature",
    ],
    "perl": [
        "function_definition",
        "package_statement",
    ],
    "julia": [
        "function_definition",
        "struct_definition",
        "module_definition",
        "macro_definition",
    ],
    "elm": [
        "function_declaration_left",
        "type_declaration",
        "type_alias_declaration",
    ],
    "fortran": [
        "function",
        "subroutine",
        "module",
        "program",
    ],
    "objc": [
        "class_interface",
        "class_implementation",
        "method_declaration",
        "protocol_declaration",
    ],
    "hack": [
        "function_declaration",
        "class_declaration",
        "interface_declaration",
        "method_declaration",
    ],
    "hcl": [
        "block",
    ],
    "sql": [
        "create_table_statement",
        "create_function_statement",
        "create_view_statement",
        "create_index_statement",
    ],
    "commonlisp": [
        "defun",
        "defclass",
        "defmethod",
        "defmacro",
    ],
    "erlang": [
        "function_clause",
        "module_attribute",
    ],
    "haskell": [
        "function",
        "type_alias",
        "newtype",
        "adt",
        "class_declaration",
        "instance_declaration",
    ],
}


def get_git_files(repo_root):
    """Get list of tracked files from git, relative to repo_root."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files failed: {result.stderr.strip()}")
    return [f for f in result.stdout.splitlines() if f]


def detect_language(filepath):
    """Detect tree-sitter language from file extension or filename."""
    p = Path(filepath)
    # Check extension first, then fall back to filename (for Dockerfile, Makefile)
    return EXT_TO_LANG.get(p.suffix) or EXT_TO_LANG.get(p.name)


def _get_signature_lines(source_lines, node, max_lines=4):
    """Extract the signature/opening lines of a definition node.

    Returns the first few lines up to the opening brace/colon/body,
    capped at max_lines. source_lines should be a pre-split list of strings.
    """
    start = node.start_point[0]
    end = node.end_point[0]

    # Determine how many lines to show
    sig_end = min(start + max_lines, end + 1, len(source_lines))

    # For nodes with a body, try to cut at the body start
    body = node.child_by_field_name("body")
    if body and body.start_point[0] > start:
        sig_end = min(body.start_point[0] + 1, sig_end)

    return source_lines[start:sig_end], start


def _is_exported(node):
    """Check if a node is exported (has export parent or export keyword)."""
    if node.parent and node.parent.type == "export_statement":
        return True
    # Check for 'export' in the node text for variable declarations
    text = node.text.decode("utf-8", errors="replace") if node.text else ""
    return text.startswith("export ")


def _should_include_node(node, lang):
    """Determine if a definition node should be included in the map."""
    node_type = node.type

    # For JS/TS export statements, include them
    if node_type == "export_statement":
        # Only include if it contains a meaningful declaration
        for child in node.children:
            if child.type in (
                "class_declaration",
                "function_declaration",
                "interface_declaration",
                "type_alias_declaration",
                "enum_declaration",
                "lexical_declaration",
                "variable_declaration",
            ):
                return True
        # export default function/class — check unnamed children too
        return any(child.type == "default" for child in node.children)

    # For variable/lexical declarations, only include top-level exported ones
    if node_type in ("lexical_declaration", "variable_declaration"):
        return _is_exported(node) or (
            node.parent and node.parent.type in ("program", "module")
        )

    return True


def extract_definitions(source_bytes, lang):
    """Parse source and extract definition signatures.

    Returns a list of (line_number, signature_lines) tuples.
    """
    try:
        parser = tree_sitter_languages.get_parser(lang)
    except Exception:
        return []

    tree = parser.parse(source_bytes)
    definitions = []
    target_types = set(DEFINITION_NODES.get(lang, []))

    if not target_types:
        return []

    source_lines = source_bytes.decode("utf-8", errors="replace").splitlines()

    def visit(node, depth=0):
        if node.type in target_types:
            if _should_include_node(node, lang):
                sig_lines, start_line = _get_signature_lines(
                    source_lines, node
                )
                definitions.append((start_line, sig_lines))

                # For classes/structs/impls, also visit children for methods
                if node.type in (
                    "class_definition",
                    "class_declaration",
                    "class_specifier",
                    "impl_item",
                    "trait_item",
                    "module",
                    "interface_declaration",
                ):
                    for child in node.children:
                        visit(child, depth + 1)
                return

        for child in node.children:
            visit(child, depth)

    visit(tree.root_node)
    definitions.sort(key=lambda d: d[0])
    return definitions


def format_file_entry(filepath, definitions):
    """Format a single file's definitions in Aider-compatible format.

    Format:
        path/to/file.ext:
        ⋮
        │def function_name(args):
        │  ...
        ⋮
    """
    if not definitions:
        return ""

    lines = [f"{filepath}:"]
    prev_end = -1

    for line_num, sig_lines in definitions:
        # Add ellipsis if there's a gap
        if line_num > prev_end + 1:
            lines.append("⋮")

        for sig_line in sig_lines:
            lines.append(f"│{sig_line}")

        prev_end = line_num + len(sig_lines)

    # Trailing ellipsis
    lines.append("⋮")
    lines.append("")

    return "\n".join(lines)


# Directories that should never be mapped — third-party/build artifacts
EXCLUDED_DIRS = {
    "node_modules",
    "vendor",
    ".vendor",
    "dist",
    "build",
    ".build",
    "out",
    ".next",
    ".nuxt",
    "__pycache__",
    ".tox",
    "venv",
    ".venv",
    "env",
    ".env",
    "site-packages",
    ".git",
    "coverage",
    ".cache",
    "bower_components",
    "jspm_packages",
    "web_modules",
}


def _is_excluded(filepath):
    """Check if a filepath falls under an excluded directory."""
    parts = Path(filepath).parts
    return any(part in EXCLUDED_DIRS for part in parts)


def generate_repo_map(repo_root, max_files=None, include_excluded=False):
    """Generate a complete repo map for the given repository.

    Args:
        repo_root: Path to the git repository root.
        max_files: Optional limit on number of files to process.
        include_excluded: If True, include files in node_modules/vendor/etc.

    Returns:
        The repo map as a string.
    """
    repo_root = Path(repo_root).resolve()
    files = get_git_files(repo_root)
    output_parts = []
    files_mapped = 0

    for filepath in sorted(files):
        if not include_excluded and _is_excluded(filepath):
            continue

        lang = detect_language(filepath)
        if lang is None:
            continue

        full_path = repo_root / filepath
        if not full_path.is_file():
            continue

        try:
            source = full_path.read_bytes()
        except (OSError, PermissionError):
            continue

        if not source.strip():
            continue

        definitions = extract_definitions(source, lang)
        if not definitions:
            continue

        entry = format_file_entry(filepath, definitions)
        if entry:
            output_parts.append(entry)
            files_mapped += 1

        if max_files and files_mapped >= max_files:
            break

    return "\n".join(output_parts)


def _parse_repo_map(content):
    """Parse a REPOMAP.md file into a dict of {filepath: entry_text}.

    Each entry runs from the filepath line through the trailing blank line.
    """
    entries = {}
    current_file = None
    current_lines = []

    for line in content.splitlines():
        # A file header is a non-empty line ending with : that doesn't start with │ or ⋮
        if (
            line.endswith(":")
            and not line.startswith("│")
            and not line.startswith("⋮")
            and not line == ""
        ):
            # Save previous entry
            if current_file is not None:
                entries[current_file] = "\n".join(current_lines)
            current_file = line[:-1]  # strip trailing :
            current_lines = [line]
        elif current_file is not None:
            current_lines.append(line)

    # Save last entry
    if current_file is not None:
        entries[current_file] = "\n".join(current_lines)

    return entries


def update_file_in_map(repo_root, filepath, map_path):
    """Incrementally update a single file's entry in an existing repo map.

    If the file has definitions, its entry is added or replaced.
    If the file has no definitions (or was deleted), its entry is removed.
    If the map file doesn't exist, a full map is generated instead.

    Args:
        repo_root: Path to the git repository root.
        filepath: Relative path to the changed file (relative to repo_root).
        map_path: Path to the REPOMAP.md file to update.

    Returns:
        True if the map was updated, False if no changes were needed.
    """
    repo_root = Path(repo_root).resolve()
    map_path = Path(map_path)

    # If no existing map, generate a full one
    if not map_path.exists():
        result = generate_repo_map(repo_root)
        if result.strip():
            map_path.write_text(result)
            return True
        return False

    # Normalize filepath to be relative to repo root
    filepath = str(filepath)

    # Parse existing map
    existing = map_path.read_text()
    entries = _parse_repo_map(existing)

    # Generate new entry for the changed file
    lang = detect_language(filepath)
    new_entry = None

    if lang is not None:
        full_path = repo_root / filepath
        if full_path.is_file():
            try:
                source = full_path.read_bytes()
                if source.strip():
                    definitions = extract_definitions(source, lang)
                    if definitions:
                        new_entry = format_file_entry(filepath, definitions)
            except (OSError, PermissionError):
                pass

    # Determine if anything changed
    old_entry = entries.get(filepath)

    if new_entry is None and old_entry is None:
        return False  # File wasn't in map and still shouldn't be

    if new_entry is not None and old_entry is not None:
        if new_entry.rstrip() == old_entry.rstrip():
            return False  # No change

    # Update the entries dict
    if new_entry is not None:
        entries[filepath] = new_entry
    elif filepath in entries:
        del entries[filepath]

    # Reassemble the map in sorted order
    sorted_entries = [entries[f] for f in sorted(entries.keys())]
    map_path.write_text("\n".join(sorted_entries))
    return True
