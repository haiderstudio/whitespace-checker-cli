# whitespace-checker-cli

Check files for bad whitespace, fail CI on trailing spaces or tabs.

[![CI](https://github.com/haiderstudio/whitespace-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/whitespace-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`whitespace_checker` reads the files or folders you name and
looks for four whitespace problems:

- trailing whitespace — a line that ends in a space or a tab
- tab character — a tab anywhere in a line
- mixed indent — a line indented with both tabs and spaces
- missing final newline — the file does not end with a newline

Every problem is reported with its file and line number, and the
tool exits 1 when any problem is found — so it can fail a CI run.
A clean tree exits 0.

- A tab inside a line is a problem because tabs render at
  different widths in different editors, so the same file looks
  different on two machines. A line indented with only tabs, or
  only spaces, is fine apart from the tab itself; a line that
  mixes the two is a separate problem, because the indent no
  longer lines up the same way everywhere.
- A file that ends without a newline is a problem because some
  tools and diffs treat the last line as incomplete.
- A line can carry more than one problem: a trailing tab is both
  trailing whitespace and a tab character, and each is reported
  on its own so the fix is clear.
- Folders are walked recursively by default (`--no-recursive`
  stops at the top level). `.git` folders are never walked, and
  directory links are never followed, so a link cycle cannot loop
  the check.
- `--exclude PATTERN` skips files by glob, for example
  `--exclude '*.min.js'`. It can be repeated.
- `--allow-tabs` skips the tab and mixed-indent checks, for a
  project that uses tabs on purpose. Trailing whitespace and the
  final newline are still checked.
- Files that are not valid UTF-8 text are skipped, not reported as
  failures — a binary file cannot hold bad whitespace. Skipped
  files are counted in the summary.
- `--stdin` checks one file piped in, `--json` prints the result as
  machine-readable JSON (the summary goes to standard error, so
  standard output stays clean JSON).
- It is report-only and runs fully offline: it never rewrites a
  file, sends nothing anywhere, and needs no API key.

## What it does NOT do

- It does not fix whitespace. A problem is reported; fixing the
  file is your job.
- It does not check anything else about a file — no syntax, no
  style, no secrets, no line length. Whitespace only.
- It does not decide your indent style. It reports tabs and mixed
  indent; whether your project uses tabs or spaces is your call,
  and `--allow-tabs` turns the tab checks off.
- It does not enforce a line-ending style. A file with Windows
  (`\r\n`) line endings passes, as long as no line ends in a
  space or a tab before the `\r\n`.

## Who it is for

Anyone who has ever had a diff full of invisible whitespace
changes: a developer adding a CI step that fails the build on a
trailing space, a team lead who keeps finding tab-indented lines
in a spaces-only codebase, or anyone who wants one small check
instead of a whitespace rule buried inside a big linter setup. If
every file is clean, you get a plain OK line; if one is not, the
report says exactly which file and line to open.

## How this differs from similar tools

The exact name `whitespace-checker-cli` matches 0 repositories
on GitHub. The unquoted search for `whitespace checker` returns
23 results, and none of them is this tool:

- The closest real rival, schorfES/node-lintspaces (31 stars),
  is a Node validator for whitespace kinds — it needs Node
  installed. This tool needs nothing beyond Python.
- The next, PHP-CS-Fixer/trailing-whitespace-checker (2 stars),
  is one check inside the PHP-CS-Fixer project, not a standalone
  command.
- The rest are a blank-string helper (14 stars), a text checker
  (0 stars), and palindrome checkers that matched the keywords
  by accident.
- The search for `trailing whitespace checker cli` returns
  1 result, a 0-star text checker — not a whitespace checker.

This tool does a narrower job: a Python standard-library-only
CLI that checks local files for trailing whitespace, tabs,
mixed indent, and a missing final newline, reports each problem
with file and line, and exits 1 for CI — no install beyond
Python, no Node, no linter, no network.

## Install

Python standard library only — no packages to download. You need
Python 3.11 or newer. Clone the repo and run it in place:

```
git clone https://github.com/haiderstudio/whitespace-checker-cli.git
cd whitespace-checker-cli
python3 src/whitespace_checker.py examples/clean.txt
```

```
OK — 1 file(s) checked, no whitespace problems.
```

## Usage

Check one file:

```
python3 src/whitespace_checker.py examples/bad-whitespace.txt
```

```
FAIL examples/bad-whitespace.txt:2: trailing whitespace
FAIL examples/bad-whitespace.txt:4: trailing whitespace
FAIL examples/bad-whitespace.txt:4: tab character
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

Check a whole folder (walked recursively):

```
python3 src/whitespace_checker.py examples/
```

```
FAIL examples/bad-whitespace.txt:2: trailing whitespace
FAIL examples/bad-whitespace.txt:4: trailing whitespace
FAIL examples/bad-whitespace.txt:4: tab character
FAIL examples/no-newline.txt:2: missing final newline
FAIL examples/tabs.txt:2: tab character
FAIL examples/tabs.txt:3: tab character
FAIL examples/tabs.txt:3: mixed indent
FAIL examples/tabs.txt:4: tab character
Checked 6 file(s), 8 problem(s) in 3 file(s).
```

Check one file from standard input (no file named reads stdin):

```
cat examples/bad-whitespace.txt | python3 src/whitespace_checker.py --stdin
```

```
FAIL <stdin>:2: trailing whitespace
FAIL <stdin>:4: trailing whitespace
FAIL <stdin>:4: tab character
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

Skip the tab checks for a project that uses tabs on purpose:

```
python3 src/whitespace_checker.py examples/tabs.txt --allow-tabs
```

```
OK — 1 file(s) checked, no whitespace problems.
```

Machine-readable output with `--json` (the summary goes to
standard error, so standard output stays clean JSON):

```
python3 src/whitespace_checker.py examples/bad-whitespace.txt --json
```

```
{
  "files": [
    {
      "file": "examples/bad-whitespace.txt",
      "problems": [
        {
          "line": 2,
          "kind": "trailing whitespace"
        },
        {
          "line": 4,
          "kind": "trailing whitespace"
        },
        {
          "line": 4,
          "kind": "tab character"
        }
      ]
    }
  ],
  "summary": {
    "checked": 1,
    "files_with_problems": 1,
    "problems": 3,
    "skipped": 0
  }
}
```

Exit codes: 0 when no problem is found, 1 when any problem is
found, 2 for a usage or input problem (a missing file, a bad flag,
no file to check).

## Examples

### 1. A file with trailing whitespace

`examples/bad-whitespace.txt` has a line ending in three spaces
and a line ending in a tab:

```
python3 src/whitespace_checker.py examples/bad-whitespace.txt
```

```
FAIL examples/bad-whitespace.txt:2: trailing whitespace
FAIL examples/bad-whitespace.txt:4: trailing whitespace
FAIL examples/bad-whitespace.txt:4: tab character
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

### 2. A file with tabs and a mixed indent

`examples/tabs.txt` has tab-indented lines and one line that
mixes a space and a tab:

```
python3 src/whitespace_checker.py examples/tabs.txt
```

```
FAIL examples/tabs.txt:2: tab character
FAIL examples/tabs.txt:3: tab character
FAIL examples/tabs.txt:3: mixed indent
FAIL examples/tabs.txt:4: tab character
Checked 1 file(s), 4 problem(s) in 1 file(s).
```

### 3. The bundled examples, all at once

```
sh examples/run-example.sh
```

The script checks the clean file (passes), then the three files
with bad whitespace (all fail, on purpose). Its full output is in
`examples/sample-output.txt`, ending with
`Checked 3 file(s), 8 problem(s) in 3 file(s).` The bad-files run
exits 1, which is the expected result — the script ends with exit
0 so it can be run as a demo.

## How it is tested

55 tests, standard library `unittest` only, no packages to install:

```
python3 tests/test_whitespace_checker.py
```

The tests cover: trailing spaces and tabs (including a blank line
full of spaces, and `\r\n` lines), tabs in the middle of a line
and as indent, mixed indent in both orders, space-only indent
passing, missing final newline (including a one-line file), an
empty file and a file of only a newline, folder walking
(recursive, `--no-recursive`, `.git` skipped, `--exclude`),
binary files skipped, stdin, `--json` output, `--allow-tabs`,
`--version`, bad flags, missing files, input files left
unchanged, the bundled examples (sample output compared
byte-for-byte against a fresh run, and the README-quoted outputs
checked against it), and hygiene checks (no placeholder text, no
absolute paths, stdlib imports only, `.env` first in `.gitignore`).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea of
checking whitespace is not new — the similar tools named above
(node-lintspaces, the PHP-CS-Fixer trailing-whitespace check)
are listed in "How this differs" — but every line of code here
is original, and the tool builds on nothing but Python's
standard library.
