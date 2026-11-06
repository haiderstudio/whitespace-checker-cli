"""Tests for whitespace_checker — standard library unittest only."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src"
EXAMPLES = ROOT / "examples"
sys.path.insert(0, str(SRC))

import whitespace_checker  # noqa: E402


def run_cli(*args, cwd=None):
    argv = [sys.executable, str(SRC / "whitespace_checker.py"), *args]
    return subprocess.run(
        argv, capture_output=True, text=True, cwd=cwd or ROOT
    )


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)
    return path


def kinds(problems):
    return [kind for _number, kind, _detail in problems]


class CheckTextTests(unittest.TestCase):
    def check(self, text, allow_tabs=False):
        return whitespace_checker.check_text(text, allow_tabs=allow_tabs)

    def test_empty_file_is_clean(self):
        self.assertEqual(self.check(""), [])

    def test_clean_file(self):
        self.assertEqual(
            self.check("one line\ntwo lines\nthree lines\n"), []
        )

    def test_single_line_with_newline_is_clean(self):
        self.assertEqual(self.check("hello\n"), [])

    def test_trailing_spaces(self):
        problems = self.check("clean line\n" + "trailing   " + "\n")
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 2)
        self.assertEqual(problems[0][1], "trailing whitespace")

    def test_trailing_tab(self):
        problems = self.check("clean line\n" + "ends with tab\t" + "\n")
        # A trailing tab is both trailing whitespace and a tab.
        self.assertEqual(len(problems), 2)
        self.assertEqual(problems[0][1], "trailing whitespace")
        self.assertEqual(problems[1][1], "tab character")

    def test_space_inside_a_line_is_not_trailing(self):
        self.assertEqual(self.check("a b c\n"), [])

    def test_blank_line_with_spaces_is_trailing(self):
        problems = self.check("one\n" + "   " + "\nthree\n")
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 2)
        self.assertEqual(problems[0][1], "trailing whitespace")

    def test_crlf_lines_are_not_trailing(self):
        self.assertEqual(self.check("one\r\ntwo\r\n"), [])

    def test_crlf_line_with_trailing_space(self):
        problems = self.check("one" + " " + "\r\ntwo\r\n")
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 1)
        self.assertEqual(problems[0][1], "trailing whitespace")

    def test_tab_in_the_middle_of_a_line(self):
        problems = self.check("a" + "\t" + "b\n")
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][1], "tab character")

    def test_tab_indent(self):
        problems = self.check("def f():\n" + "\t" + "return 1\n")
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 2)
        self.assertEqual(problems[0][1], "tab character")

    def test_mixed_indent_space_then_tab(self):
        problems = self.check(" " + "\t" + "mixed\n")
        self.assertEqual(kinds(problems), ["tab character", "mixed indent"])

    def test_mixed_indent_tab_then_space(self):
        problems = self.check("\t" + " " + "mixed\n")
        self.assertEqual(kinds(problems), ["tab character", "mixed indent"])

    def test_space_only_indent_is_clean(self):
        self.assertEqual(self.check("    indented\n        more\n"), [])

    def test_tab_only_indent_is_one_problem(self):
        problems = self.check("\t" + "indented\n")
        self.assertEqual(kinds(problems), ["tab character"])

    def test_mixed_indent_needs_content(self):
        # A blank line of mixed whitespace is trailing whitespace
        # only, not a mixed indent.
        problems = self.check(" " + "\t" + "\n")
        self.assertEqual(kinds(problems), ["trailing whitespace", "tab character"])

    def test_missing_final_newline(self):
        problems = self.check("one\ntwo")
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 2)
        self.assertEqual(problems[0][1], "missing final newline")

    def test_missing_final_newline_single_line(self):
        problems = self.check("only one line")
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0][0], 1)
        self.assertEqual(problems[0][1], "missing final newline")

    def test_file_of_only_a_newline_is_clean(self):
        self.assertEqual(self.check("\n"), [])

    def test_problems_are_in_line_order(self):
        problems = self.check("bad" + " " + "\n" + "\t" + "tab\nno newline")
        self.assertEqual(
            [(number, kind) for number, kind, _d in problems],
            [
                (1, "trailing whitespace"),
                (2, "tab character"),
                (3, "missing final newline"),
            ],
        )

    def test_allow_tabs_skips_tab_and_mixed(self):
        problems = self.check("\t" + "tabbed\n" + " \t" + "mixed\n",
                               allow_tabs=True)
        self.assertEqual(problems, [])

    def test_allow_tabs_keeps_trailing_and_newline(self):
        problems = self.check("bad" + " " + "\nno newline",
                              allow_tabs=True)
        self.assertEqual(kinds(problems),
                         ["trailing whitespace", "missing final newline"])


class CollectFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            whitespace_checker.collect_files(["no-such-file.txt"])

    def test_files_and_folders_mix(self):
        write(self.tmp.name, "a.txt", "clean\n")
        write(self.tmp.name, "sub/b.txt", "clean\n")
        files = whitespace_checker.collect_files(
            [str(Path(self.tmp.name) / "a.txt"), self.tmp.name]
        )
        self.assertEqual(len(files), 3)

    def test_no_recursive_flag(self):
        write(self.tmp.name, "a.txt", "clean\n")
        write(self.tmp.name, "sub/b.txt", "clean\n")
        files = whitespace_checker.collect_files(
            [self.tmp.name], recursive=False
        )
        self.assertEqual([p.name for p in files], ["a.txt"])

    def test_git_folder_is_never_walked(self):
        write(self.tmp.name, ".git/hooks/sample.txt", "bad" + " " + "\n")
        write(self.tmp.name, "a.txt", "clean\n")
        files = whitespace_checker.collect_files([self.tmp.name])
        self.assertEqual([p.name for p in files], ["a.txt"])

    def test_exclude_by_name(self):
        write(self.tmp.name, "a.txt", "clean\n")
        write(self.tmp.name, "skip.log", "bad" + " " + "\n")
        files = whitespace_checker.collect_files(
            [self.tmp.name], excludes=["*.log"]
        )
        self.assertEqual([p.name for p in files], ["a.txt"])

    def test_binary_file_is_skipped_not_failed(self):
        path = Path(self.tmp.name) / "bin.dat"
        path.write_bytes(b"\x00\x01\x02\xff")
        write(self.tmp.name, "a.txt", "clean\n")
        results, skipped = whitespace_checker.check_files(
            [path, Path(self.tmp.name) / "a.txt"]
        )
        self.assertEqual(skipped, 1)
        self.assertEqual(results[Path(self.tmp.name) / "a.txt"], [])

    def test_summarize(self):
        results = {
            Path("a.txt"): [(1, "trailing whitespace", "x")],
            Path("b.txt"): [],
        }
        summary = whitespace_checker.summarize(results, skipped=1)
        self.assertEqual(
            summary,
            {
                "checked": 2,
                "files_with_problems": 1,
                "problems": 1,
                "skipped": 1,
            },
        )

    def test_format_problems_sorted_by_file(self):
        results = {
            Path("b.txt"): [(2, "tab character", "x")],
            Path("a.txt"): [(1, "trailing whitespace", "x")],
        }
        lines = whitespace_checker.format_problems(results)
        self.assertEqual(
            lines,
            [
                "FAIL a.txt:1: trailing whitespace",
                "FAIL b.txt:2: tab character",
            ],
        )


class CliTests(unittest.TestCase):
    def test_clean_file_passes(self):
        result = run_cli("examples/clean.txt")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            "OK — 1 file(s) checked, no whitespace problems.\n",
        )

    def test_bad_file_fails(self):
        result = run_cli("examples/bad-whitespace.txt")
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "FAIL examples/bad-whitespace.txt:2: trailing whitespace",
            result.stdout,
        )
        self.assertIn(
            "Checked 1 file(s), 3 problem(s) in 1 file(s).", result.stdout
        )

    def test_tabs_file_fails(self):
        result = run_cli("examples/tabs.txt")
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL examples/tabs.txt:3: mixed indent", result.stdout)
        self.assertIn(
            "Checked 1 file(s), 4 problem(s) in 1 file(s).", result.stdout
        )

    def test_no_newline_file_fails(self):
        result = run_cli("examples/no-newline.txt")
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "FAIL examples/no-newline.txt:2: missing final newline",
            result.stdout,
        )

    def test_folder_argument(self):
        result = run_cli("examples/")
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "Checked 6 file(s), 8 problem(s) in 3 file(s).", result.stdout
        )

    def test_allow_tabs_flag(self):
        result = run_cli("examples/tabs.txt", "--allow-tabs")
        self.assertEqual(result.returncode, 0)
        self.assertIn("no whitespace problems", result.stdout)

    def test_stdin(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SRC / "whitespace_checker.py"),
                "--stdin",
            ],
            input="bad" + " " + "\n",
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL <stdin>:1: trailing whitespace", result.stdout)

    def test_stdin_clean(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SRC / "whitespace_checker.py"),
                "--stdin",
            ],
            input="clean\n",
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("no whitespace problems", result.stdout)

    def test_stdin_with_paths_is_usage_error(self):
        result = run_cli("examples/clean.txt", "--stdin")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--stdin cannot be combined", result.stderr)

    def test_missing_file_is_usage_error(self):
        result = run_cli("no-such-file.txt")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no such file or folder", result.stderr)

    def test_empty_folder_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli(tmp)
        self.assertEqual(result.returncode, 2)
        self.assertIn("no files to check", result.stderr)

    def test_bad_flag_is_usage_error(self):
        result = run_cli("--no-such-flag")
        self.assertEqual(result.returncode, 2)

    def test_json_output(self):
        result = run_cli("examples/bad-whitespace.txt", "--json")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["problems"], 3)
        self.assertEqual(payload["summary"]["checked"], 1)
        self.assertEqual(len(payload["files"]), 1)
        self.assertEqual(
            payload["files"][0]["problems"][0],
            {"line": 2, "kind": "trailing whitespace"},
        )
        self.assertIn("Checked 1 file(s)", result.stderr)

    def test_json_clean(self):
        result = run_cli("examples/clean.txt", "--json")
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["files"], [])
        self.assertEqual(payload["summary"]["problems"], 0)

    def test_exclude_flag(self):
        result = run_cli("examples/", "--exclude", "tabs.txt")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("tabs.txt", result.stdout)
        self.assertIn(
            "Checked 5 file(s), 4 problem(s) in 2 file(s).", result.stdout
        )

    def test_no_recursive_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "top.txt", "bad" + " " + "\n")
            write(tmp, "sub/deep.txt", "bad" + " " + "\n")
            result = run_cli(tmp, "--no-recursive")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Checked 1 file(s)", result.stdout)

    def test_input_files_are_not_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.txt", "bad" + " " + "\nno newline")
            before = path.read_bytes()
            result = run_cli(str(path))
            self.assertEqual(result.returncode, 1)
            self.assertEqual(path.read_bytes(), before)

    def test_version_flag(self):
        result = run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("whitespace_checker 1.0.0", result.stdout)

    def test_sample_output_matches_a_fresh_run(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout, (EXAMPLES / "sample-output.txt").read_text()
        )

    def test_run_example_script_exits_zero(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)


class HygieneTests(unittest.TestCase):
    """The template gate: no placeholder text, no secrets, no local
    paths, stdlib imports only. The scan skips .git and __pycache__
    (Day 21 rule) and skips tests/ itself (Day 22 pattern), because
    this file's own banned-word list would otherwise trip it."""

    BANNED = ("TODO", "FIXME", "coming soon", "lorem", "API_KEY")

    def _repo_files(self):
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            yield path

    def test_no_placeholder_text(self):
        hits = []
        for path in self._repo_files():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for word in self.BANNED:
                if word in text:
                    hits.append(f"{path.relative_to(ROOT)}: {word}")
        self.assertEqual(hits, [])

    def test_no_absolute_local_paths(self):
        hits = []
        for path in self._repo_files():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if "/home/" in text or "/Users/" in text or "C:\\" in text:
                hits.append(str(path.relative_to(ROOT)))
        self.assertEqual(hits, [])

    def test_stdlib_only_imports(self):
        import ast

        allowed = {
            "argparse",
            "contextlib",
            "fnmatch",
            "json",
            "sys",
            "pathlib",
            # Test file only: unittest, io, os, tempfile, subprocess.
            "io",
            "os",
            "subprocess",
            "tempfile",
            "unittest",
        }
        src = ROOT / "src" / "whitespace_checker.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])
        self.assertEqual(imported - allowed, set())

    def test_gitignore_lists_env_first(self):
        lines = (ROOT / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_readme_quoted_outputs_are_real(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn(
            "FAIL examples/bad-whitespace.txt:2: trailing whitespace",
            readme,
        )
        self.assertIn("Checked 6 file(s), 8 problem(s) in 3 file(s).", readme)
        self.assertIn(
            "OK — 1 file(s) checked, no whitespace problems.", readme
        )


if __name__ == "__main__":
    unittest.main()
