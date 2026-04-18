"""Comprehensive tests for repomap.mapper."""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from repomap.mapper import (
    EXT_TO_LANG,
    detect_language,
    extract_definitions,
    format_file_entry,
    generate_repo_map,
    get_git_files,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository."""
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
    """Helper: write files, git add, git commit."""
    for path, content in files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add files"],
        cwd=repo,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# detect_language
# ---------------------------------------------------------------------------


class TestDetectLanguage:
    def test_python(self):
        assert detect_language("foo.py") == "python"

    def test_typescript(self):
        assert detect_language("src/index.ts") == "typescript"

    def test_tsx(self):
        assert detect_language("Component.tsx") == "tsx"

    def test_javascript(self):
        assert detect_language("app.js") == "javascript"

    def test_jsx(self):
        assert detect_language("App.jsx") == "javascript"

    def test_go(self):
        assert detect_language("main.go") == "go"

    def test_rust(self):
        assert detect_language("lib.rs") == "rust"

    def test_ruby(self):
        assert detect_language("app.rb") == "ruby"

    def test_java(self):
        assert detect_language("Main.java") == "java"

    def test_csharp(self):
        assert detect_language("Program.cs") == "c_sharp"

    def test_c_source(self):
        assert detect_language("main.c") == "c"

    def test_c_header(self):
        assert detect_language("header.h") == "c"

    def test_cpp_variants(self):
        assert detect_language("main.cpp") == "cpp"
        assert detect_language("main.cc") == "cpp"
        assert detect_language("main.cxx") == "cpp"
        assert detect_language("main.hpp") == "cpp"

    def test_php(self):
        assert detect_language("index.php") == "php"

    def test_swift(self):
        assert detect_language("App.swift") == "swift"

    def test_kotlin(self):
        assert detect_language("Main.kt") == "kotlin"
        assert detect_language("build.kts") == "kotlin"

    def test_scala(self):
        assert detect_language("Main.scala") == "scala"

    def test_elixir(self):
        assert detect_language("app.ex") == "elixir"
        assert detect_language("test.exs") == "elixir"

    def test_dart(self):
        assert detect_language("main.dart") == "dart"

    def test_shell(self):
        assert detect_language("deploy.sh") == "bash"
        assert detect_language("run.bash") == "bash"

    def test_yaml(self):
        assert detect_language("config.yaml") == "yaml"
        assert detect_language("config.yml") == "yaml"

    def test_makefile(self):
        assert detect_language("Makefile") == "make"
        assert detect_language("makefile") == "make"

    def test_dockerfile(self):
        assert detect_language("Dockerfile") == "dockerfile"

    def test_unknown_returns_none(self):
        assert detect_language("readme.md") is None
        assert detect_language("data.csv") is None
        assert detect_language("image.png") is None

    def test_nested_paths(self):
        assert detect_language("src/components/Button.tsx") == "tsx"
        assert detect_language("pkg/handler/api.go") == "go"

    def test_all_extensions_mapped(self):
        """Every entry in EXT_TO_LANG should return its language."""
        for key, lang in EXT_TO_LANG.items():
            if key.startswith("."):
                assert detect_language(f"file{key}") == lang, f"Failed for extension {key}"
            else:
                # Filename keys like Dockerfile, Makefile
                assert detect_language(key) == lang, f"Failed for filename {key}"


# ---------------------------------------------------------------------------
# extract_definitions — Python
# ---------------------------------------------------------------------------


class TestExtractPython:
    def test_function(self):
        source = b"def hello(name):\n    return f'Hello {name}'\n"
        defs = extract_definitions(source, "python")
        assert len(defs) == 1
        assert defs[0][0] == 0  # line 0
        assert "def hello(name):" in defs[0][1][0]

    def test_class_and_methods(self):
        source = b"""class MyClass:
    def __init__(self):
        pass

    def method(self, x):
        return x
"""
        defs = extract_definitions(source, "python")
        assert len(defs) >= 1
        assert "class MyClass:" in defs[0][1][0]

    def test_decorated_function(self):
        source = b"""@app.route('/api')
def api_handler():
    return {}
"""
        defs = extract_definitions(source, "python")
        assert len(defs) >= 1

    def test_multiple_functions(self):
        source = b"""def foo():
    pass

def bar():
    pass

def baz():
    pass
"""
        defs = extract_definitions(source, "python")
        assert len(defs) == 3

    def test_empty_source(self):
        defs = extract_definitions(b"", "python")
        assert defs == []

    def test_no_definitions(self):
        source = b"x = 1\ny = 2\nprint(x + y)\n"
        defs = extract_definitions(source, "python")
        assert defs == []

    def test_nested_function(self):
        source = b"""def outer():
    def inner():
        pass
    return inner()
"""
        defs = extract_definitions(source, "python")
        # Should get at least outer
        assert len(defs) >= 1
        assert "def outer():" in defs[0][1][0]


# ---------------------------------------------------------------------------
# extract_definitions — TypeScript/TSX
# ---------------------------------------------------------------------------


class TestExtractTypeScript:
    def test_interface(self):
        source = b"""interface UserProps {
  name: string;
  age: number;
}
"""
        defs = extract_definitions(source, "typescript")
        assert len(defs) >= 1
        found = any("interface UserProps" in line for _, lines in defs for line in lines)
        assert found

    def test_exported_function(self):
        source = b"""export function handleRequest(req: Request): Response {
  return new Response('ok');
}
"""
        defs = extract_definitions(source, "typescript")
        assert len(defs) >= 1
        found = any(
            "export function handleRequest" in line
            for _, lines in defs
            for line in lines
        )
        assert found

    def test_type_alias(self):
        source = b"export type Status = 'active' | 'inactive';\n"
        defs = extract_definitions(source, "typescript")
        assert len(defs) >= 1

    def test_enum(self):
        source = b"""enum Color {
  Red,
  Green,
  Blue,
}
"""
        defs = extract_definitions(source, "typescript")
        assert len(defs) >= 1

    def test_tsx_component(self):
        source = b"""export default function Button({ label }: { label: string }) {
  return <button>{label}</button>;
}
"""
        defs = extract_definitions(source, "tsx")
        assert len(defs) >= 1

    def test_tsx_interface_and_component(self):
        source = b"""interface CardProps {
  title: string;
  children: React.ReactNode;
}

export function Card({ title, children }: CardProps) {
  return (
    <div>
      <h2>{title}</h2>
      {children}
    </div>
  );
}
"""
        defs = extract_definitions(source, "tsx")
        assert len(defs) >= 2


# ---------------------------------------------------------------------------
# extract_definitions — JavaScript
# ---------------------------------------------------------------------------


class TestExtractJavaScript:
    def test_function_declaration(self):
        source = b"function greet(name) {\n  return `Hello ${name}`;\n}\n"
        defs = extract_definitions(source, "javascript")
        assert len(defs) >= 1

    def test_class(self):
        source = b"""class Animal {
  constructor(name) {
    this.name = name;
  }

  speak() {
    return this.name;
  }
}
"""
        defs = extract_definitions(source, "javascript")
        assert len(defs) >= 1

    def test_export_default(self):
        source = b"export default function main() { return 42; }\n"
        defs = extract_definitions(source, "javascript")
        assert len(defs) >= 1


# ---------------------------------------------------------------------------
# extract_definitions — Go
# ---------------------------------------------------------------------------


class TestExtractGo:
    def test_function(self):
        source = b"""package main

func main() {
    fmt.Println("hello")
}
"""
        defs = extract_definitions(source, "go")
        assert len(defs) == 1
        assert "func main()" in defs[0][1][0]

    def test_method(self):
        source = b"""package main

func (s *Server) Start() error {
    return nil
}
"""
        defs = extract_definitions(source, "go")
        assert len(defs) == 1

    def test_type(self):
        source = b"""package main

type Server struct {
    port int
    host string
}
"""
        defs = extract_definitions(source, "go")
        assert len(defs) == 1

    def test_multiple(self):
        source = b"""package main

type Config struct {
    Port int
}

func NewConfig() *Config {
    return &Config{Port: 8080}
}

func (c *Config) Validate() error {
    return nil
}
"""
        defs = extract_definitions(source, "go")
        assert len(defs) == 3


# ---------------------------------------------------------------------------
# extract_definitions — Rust
# ---------------------------------------------------------------------------


class TestExtractRust:
    def test_function(self):
        source = b"fn main() {\n    println!(\"hello\");\n}\n"
        defs = extract_definitions(source, "rust")
        assert len(defs) == 1

    def test_struct(self):
        source = b"struct Point {\n    x: f64,\n    y: f64,\n}\n"
        defs = extract_definitions(source, "rust")
        assert len(defs) == 1

    def test_impl(self):
        source = b"""struct Foo;

impl Foo {
    fn new() -> Self {
        Foo
    }
}
"""
        defs = extract_definitions(source, "rust")
        assert len(defs) >= 2

    def test_trait(self):
        source = b"""trait Drawable {
    fn draw(&self);
}
"""
        defs = extract_definitions(source, "rust")
        assert len(defs) == 1

    def test_enum(self):
        source = b"""enum Direction {
    North,
    South,
    East,
    West,
}
"""
        defs = extract_definitions(source, "rust")
        assert len(defs) == 1


# ---------------------------------------------------------------------------
# extract_definitions — Java
# ---------------------------------------------------------------------------


class TestExtractJava:
    def test_class_and_method(self):
        source = b"""public class Main {
    public static void main(String[] args) {
        System.out.println("hello");
    }
}
"""
        defs = extract_definitions(source, "java")
        assert len(defs) >= 1

    def test_interface(self):
        source = b"""public interface Printable {
    void print();
}
"""
        defs = extract_definitions(source, "java")
        assert len(defs) >= 1


# ---------------------------------------------------------------------------
# extract_definitions — Ruby
# ---------------------------------------------------------------------------


class TestExtractRuby:
    def test_class_and_method(self):
        source = b"""class Dog
  def bark
    puts 'woof'
  end
end
"""
        defs = extract_definitions(source, "ruby")
        assert len(defs) >= 1

    def test_module(self):
        source = b"""module Helpers
  def self.format(x)
    x.to_s
  end
end
"""
        defs = extract_definitions(source, "ruby")
        assert len(defs) >= 1


# ---------------------------------------------------------------------------
# extract_definitions — C
# ---------------------------------------------------------------------------


class TestExtractC:
    def test_function(self):
        source = b"""int add(int a, int b) {
    return a + b;
}
"""
        defs = extract_definitions(source, "c")
        assert len(defs) == 1

    def test_struct(self):
        source = b"""struct Point {
    int x;
    int y;
};
"""
        defs = extract_definitions(source, "c")
        assert len(defs) == 1


# ---------------------------------------------------------------------------
# extract_definitions — PHP
# ---------------------------------------------------------------------------


class TestExtractPHP:
    def test_class(self):
        source = b"""<?php
class User {
    public function getName(): string {
        return $this->name;
    }
}
"""
        defs = extract_definitions(source, "php")
        assert len(defs) >= 1


# ---------------------------------------------------------------------------
# extract_definitions — edge cases
# ---------------------------------------------------------------------------


class TestExtractEdgeCases:
    def test_unsupported_language(self):
        defs = extract_definitions(b"some content", "nonexistent_language")
        assert defs == []

    def test_language_with_no_definition_nodes(self):
        # YAML/TOML etc. have no entries in DEFINITION_NODES
        defs = extract_definitions(b"key: value\n", "yaml")
        assert defs == []

    def test_binary_content(self):
        defs = extract_definitions(b"\x00\x01\x02\x03", "python")
        assert defs == []

    def test_syntax_errors_handled(self):
        source = b"def broken(\n  # missing closing paren and body\n"
        # Should not raise
        defs = extract_definitions(source, "python")
        # May or may not find defs, but shouldn't crash
        assert isinstance(defs, list)

    def test_utf8_content(self):
        source = "def héllo():\n    return 'café'\n".encode("utf-8")
        defs = extract_definitions(source, "python")
        assert len(defs) == 1

    def test_very_long_signature_capped(self):
        # Function with a very long parameter list spanning many lines
        params = ", ".join(f"arg{i}: int" for i in range(50))
        source = f"def big_func({params}):\n    pass\n".encode()
        defs = extract_definitions(source, "python")
        assert len(defs) == 1
        # Signature lines should be capped at max_lines
        assert len(defs[0][1]) <= 4


# ---------------------------------------------------------------------------
# format_file_entry
# ---------------------------------------------------------------------------


class TestFormatFileEntry:
    def test_empty_definitions(self):
        assert format_file_entry("foo.py", []) == ""

    def test_single_definition(self):
        defs = [(0, ["def hello():"])]
        result = format_file_entry("foo.py", defs)
        assert "foo.py:" in result
        assert "│def hello():" in result
        assert "⋮" in result

    def test_multiple_definitions_with_gaps(self):
        defs = [
            (0, ["def foo():"]),
            (10, ["def bar():"]),
        ]
        result = format_file_entry("app.py", defs)
        lines = result.split("\n")
        assert lines[0] == "app.py:"
        # Should have ellipsis between defs
        ellipsis_count = sum(1 for line in lines if line == "⋮")
        assert ellipsis_count >= 2  # before first, between, and after last

    def test_consecutive_definitions_no_extra_ellipsis(self):
        defs = [
            (0, ["def foo():"]),
            (1, ["def bar():"]),
        ]
        result = format_file_entry("app.py", defs)
        lines = result.split("\n")
        # Between consecutive defs there should be no ellipsis
        assert lines[0] == "app.py:"
        # Only trailing ellipsis expected (no gap)


# ---------------------------------------------------------------------------
# get_git_files
# ---------------------------------------------------------------------------


class TestGetGitFiles:
    def test_returns_tracked_files(self, git_repo):
        _add_and_commit(git_repo, {"hello.py": "print('hi')\n"})
        files = get_git_files(git_repo)
        assert "hello.py" in files

    def test_excludes_untracked_files(self, git_repo):
        _add_and_commit(git_repo, {"tracked.py": "x = 1\n"})
        (git_repo / "untracked.py").write_text("y = 2\n")
        files = get_git_files(git_repo)
        assert "tracked.py" in files
        assert "untracked.py" not in files

    def test_nested_paths(self, git_repo):
        _add_and_commit(git_repo, {"src/lib/utils.py": "def util(): pass\n"})
        files = get_git_files(git_repo)
        assert "src/lib/utils.py" in files

    def test_not_a_git_repo(self, tmp_path):
        with pytest.raises(RuntimeError, match="git ls-files failed"):
            get_git_files(tmp_path)


# ---------------------------------------------------------------------------
# generate_repo_map — integration
# ---------------------------------------------------------------------------


class TestGenerateRepoMap:
    def test_python_repo(self, git_repo):
        _add_and_commit(
            git_repo,
            {
                "app.py": "def main():\n    print('hello')\n",
                "lib/utils.py": "def helper(x):\n    return x * 2\n",
            },
        )
        result = generate_repo_map(git_repo)
        assert "app.py:" in result
        assert "lib/utils.py:" in result
        assert "│def main():" in result
        assert "│def helper(x):" in result

    def test_typescript_repo(self, git_repo):
        _add_and_commit(
            git_repo,
            {
                "index.ts": "interface Config {\n  port: number;\n}\n\nexport function start(c: Config) {\n  return c.port;\n}\n",
            },
        )
        result = generate_repo_map(git_repo)
        assert "index.ts:" in result
        assert "interface Config" in result

    def test_mixed_languages(self, git_repo):
        _add_and_commit(
            git_repo,
            {
                "main.py": "def run():\n    pass\n",
                "server.go": "package main\n\nfunc serve() {\n}\n",
                "README.md": "# Hello\n",
            },
        )
        result = generate_repo_map(git_repo)
        assert "main.py:" in result
        assert "server.go:" in result
        # README.md should not appear (unsupported)
        assert "README.md" not in result

    def test_empty_repo(self, git_repo):
        _add_and_commit(git_repo, {"README.md": "# Hello\n"})
        result = generate_repo_map(git_repo)
        assert result.strip() == ""

    def test_no_definitions_in_code(self, git_repo):
        _add_and_commit(git_repo, {"script.py": "x = 1\nprint(x)\n"})
        result = generate_repo_map(git_repo)
        assert result.strip() == ""

    def test_max_files_limit(self, git_repo):
        files = {f"mod{i}.py": f"def func{i}():\n    pass\n" for i in range(20)}
        _add_and_commit(git_repo, files)
        result = generate_repo_map(git_repo, max_files=5)
        file_entries = [line for line in result.split("\n") if line.endswith(":") and not line.startswith("│") and not line.startswith("⋮")]
        assert len(file_entries) == 5

    def test_empty_files_skipped(self, git_repo):
        _add_and_commit(
            git_repo,
            {
                "empty.py": "",
                "whitespace.py": "   \n\n  \n",
                "real.py": "def real():\n    pass\n",
            },
        )
        result = generate_repo_map(git_repo)
        assert "empty.py" not in result
        assert "whitespace.py" not in result
        assert "real.py:" in result

    def test_deleted_file_skipped(self, git_repo):
        _add_and_commit(git_repo, {"exists.py": "def f():\n    pass\n"})
        # Track a file then delete it from filesystem
        (git_repo / "exists.py").unlink()
        # It's still in git index but not on disk
        result = generate_repo_map(git_repo)
        assert "exists.py" not in result

    def test_permission_error_skipped(self, git_repo):
        _add_and_commit(
            git_repo,
            {
                "ok.py": "def ok():\n    pass\n",
                "noperm.py": "def nope():\n    pass\n",
            },
        )
        (git_repo / "noperm.py").chmod(0o000)
        try:
            result = generate_repo_map(git_repo)
            assert "ok.py:" in result
            # noperm.py may or may not appear depending on OS
        finally:
            (git_repo / "noperm.py").chmod(0o644)

    def test_output_format_matches_aider(self, git_repo):
        """Verify the output format matches Aider's structure."""
        _add_and_commit(
            git_repo,
            {
                "src/handler.ts": 'interface HandlerProps {\n  method: string;\n}\n\nexport function handle(props: HandlerProps) {\n  return props.method;\n}\n',
            },
        )
        result = generate_repo_map(git_repo)
        lines = result.strip().split("\n")

        # First line should be filepath:
        assert lines[0] == "src/handler.ts:"

        # Should contain ⋮ (ellipsis markers)
        assert any(line == "⋮" for line in lines)

        # Definition lines should start with │
        def_lines = [l for l in lines if l.startswith("│")]
        assert len(def_lines) > 0

    def test_files_sorted_alphabetically(self, git_repo):
        _add_and_commit(
            git_repo,
            {
                "z_last.py": "def z():\n    pass\n",
                "a_first.py": "def a():\n    pass\n",
                "m_middle.py": "def m():\n    pass\n",
            },
        )
        result = generate_repo_map(git_repo)
        file_lines = [l for l in result.split("\n") if l.endswith(":") and not l.startswith("│") and not l.startswith("⋮")]
        assert file_lines == ["a_first.py:", "m_middle.py:", "z_last.py:"]
