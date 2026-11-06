#!/usr/bin/env python3
"""Check files for bad whitespace, fail CI on trailing spaces or tabs.

Run: python3 src/whitespace_checker.py examples/clean.txt
     python3 src/whitespace_checker.py src/ docs/
     cat file.txt | python3 src/whitespace_checker.py --stdin

The tool reads each file and looks for four whitespace problems:

    trailing whitespace   a line that ends in a space or a tab
    tab character         a tab anywhere in a line
    mixed indent          a line indented with both tabs and spaces
    missing final newline the file does not end with a newline

Every problem is reported with its file and line number. The tool
exits 1 when any problem is found — so it can fail a CI run — and 0
when every file is clean.

A tab inside a line is a problem because tabs render at different
widths in different editors, so the same file looks different on
two machines. A line indented with only tabs, or only spaces, is
fine apart from the tab itself; a line that mixes the two is a
separate problem, because the indent no longer lines up the same
way everywhere. A file that ends without a newline is a problem
because some tools and diffs treat the last line as incomplete.

It never rewrites a file. It is report-only and runs fully offline:
it sends nothing anywhere and needs no API key.

Exit codes: 0 when no problem is found, 1 when any problem is
found, 2 for a usage or input problem (a missing file, a bad flag,
no file to check).

Python standard library only.
"""

import argparse
import contextlib
import fnmatch
import json
import sys
from pathlib import Path

VERSION = "1.0.0"


def check_text(text, allow_tabs=False):
    """Find every whitespace problem in one file's text.

    Returns a list of (line_number, kind, detail) tuples, in line
    order. A line can carry more than one problem: a trailing tab is
    both trailing whitespace and a tab character, and each is
    reported on its own so the fix is clear.
    """
    problems = []
    if text == "":
        return problems
    ends_with_newline = text.endswith("\n")
    lines = text.split("\n")
    if ends_with_newline:
        # The split leaves one empty piece after the final newline;
        # it is not a line of the file.
        lines = lines[:-1]
    for number, raw in enumerate(lines, start=1):
        line = raw[:-1] if raw.endswith("\r") else raw
        if line.endswith(" ") or line.endswith("\t"):
            problems.append((number, "trailing whitespace", line))
        if not allow_tabs:
            if "\t" in line:
                problems.append((number, "tab character", line))
            stripped = line.lstrip(" \t")
            if stripped:
                indent = line[: len(line) - len(stripped)]
                if " " in indent and "\t" in indent:
                    problems.append((number, "mixed indent", line))
    if not ends_with_newline:
        problems.append(
            (len(lines), "missing final newline", lines[-1] if lines else "")
        )
    return problems


def is_text_file(path):
    """True when a file can be read as UTF-8 text.

    Files that are not valid UTF-8 are binary for this tool's purpose
    and are skipped, not reported as failures.
    """
    try:
        path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return True


def collect_files(paths, recursive=True, excludes=()):
    """Turn file and folder arguments into a sorted list of files.

    Folders are walked (recursively unless --no-recursive), `.git`
    folders are never walked, and directory links are never followed,
    so a link cycle cannot loop the check. Files matching an
    --exclude glob (checked against the name and the path) are left
    out.
    """
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            if not _excluded(path, excludes):
                found.append(path)
        elif path.is_dir():
            if recursive:
                for root, dirs, files in path.walk():
                    dirs[:] = sorted(d for d in dirs if d != ".git")
                    for name in sorted(files):
                        candidate = root / name
                        if not _excluded(candidate, excludes):
                            found.append(candidate)
            else:
                for child in sorted(path.iterdir()):
                    if child.is_file() and not _excluded(child, excludes):
                        found.append(child)
        else:
            raise FileNotFoundError(raw)
    return found


def _excluded(path, excludes):
    name = path.name
    text = str(path)
    return any(
        fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(text, pattern)
        for pattern in excludes
    )


def check_files(files, allow_tabs=False):
    """Check each file. Returns (results, skipped).

    results maps each checked file to its list of problems.
    skipped counts the files left out because they are not UTF-8 text.
    """
    results = {}
    skipped = 0
    for path in files:
        if not is_text_file(path):
            skipped += 1
            continue
        text = path.read_text(encoding="utf-8")
        results[path] = check_text(text, allow_tabs=allow_tabs)
    return results, skipped


def summarize(results, skipped):
    """Build the summary numbers from per-file results."""
    checked = len(results)
    bad_files = sum(1 for problems in results.values() if problems)
    problems = sum(len(items) for items in results.values())
    return {
        "checked": checked,
        "files_with_problems": bad_files,
        "problems": problems,
        "skipped": skipped,
    }


def format_problems(results):
    """Format the per-problem FAIL lines, in file order."""
    lines = []
    for path in sorted(results, key=str):
        for number, kind, _detail in results[path]:
            lines.append(f"FAIL {path}:{number}: {kind}")
    return lines


def run(argv=None, stdin_text=None, stdout=None, stderr=None):
    """Run the CLI. Returns the exit code."""
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr

    parser = argparse.ArgumentParser(
        prog="whitespace_checker",
        description=(
            "Check files for bad whitespace, fail CI on trailing "
            "spaces or tabs."
        ),
    )
    parser.add_argument(
        "paths", nargs="*", help="files or folders to check (default: .)"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="read one file from standard input instead of paths",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="do not walk into subfolders of a named folder",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="skip files matching this glob (repeatable)",
    )
    parser.add_argument(
        "--allow-tabs",
        action="store_true",
        help="do not report tab characters or mixed indent",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON on stdout",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {VERSION}"
    )
    # argparse exits (SystemExit) on --version and on bad flags. Catch
    # it so the message lands in the caller's streams and run() returns
    # the code instead of raising.
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
            stderr
        ):
            args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    if args.stdin and args.paths:
        print(
            "error: --stdin cannot be combined with file paths", file=stderr
        )
        return 2
    if args.stdin:
        if stdin_text is None:
            stdin_text = sys.stdin.read()
        results = {
            "<stdin>": check_text(stdin_text, allow_tabs=args.allow_tabs)
        }
        skipped = 0
    else:
        paths = args.paths if args.paths else ["."]
        try:
            files = collect_files(
                paths,
                recursive=not args.no_recursive,
                excludes=args.exclude,
            )
        except FileNotFoundError as exc:
            print(f"error: no such file or folder: {exc}", file=stderr)
            return 2
        if not files:
            print("error: no files to check", file=stderr)
            return 2
        results, skipped = check_files(files, allow_tabs=args.allow_tabs)

    summary = summarize(results, skipped)

    if args.json:
        payload = {
            "files": [
                {
                    "file": str(path),
                    "problems": [
                        {"line": number, "kind": kind}
                        for number, kind, _detail in results[path]
                    ],
                }
                for path in sorted(results, key=str)
                if results[path]
            ],
            "summary": summary,
        }
        print(json.dumps(payload, indent=2), file=stdout)
    else:
        for line in format_problems(results):
            print(line, file=stdout)

    if summary["problems"] == 0:
        checked = summary["checked"]
        line = f"OK — {checked} file(s) checked, no whitespace problems."
        if skipped:
            line += f" ({skipped} non-text file(s) skipped.)"
        print(line, file=stderr if args.json else stdout)
        return 0

    line = (
        f"Checked {summary['checked']} file(s), "
        f"{summary['problems']} problem(s) in "
        f"{summary['files_with_problems']} file(s)."
    )
    if skipped:
        line += f" ({skipped} non-text file(s) skipped.)"
    print(line, file=stderr if args.json else stdout)
    return 1


def main():
    sys.exit(run())


if __name__ == "__main__":
    main()
