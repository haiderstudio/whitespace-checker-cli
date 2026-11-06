#!/bin/sh
# Run the checker on the bundled examples.
# Run from the repo root: sh examples/run-example.sh
# The check run exits 1 because three example files carry bad
# whitespace on purpose — that is the expected result here.
set -e
cd "$(dirname "$0")/.."
echo "--- check the clean file ---"
python3 src/whitespace_checker.py examples/clean.txt
echo "--- check the files with bad whitespace ---"
python3 src/whitespace_checker.py examples/bad-whitespace.txt examples/tabs.txt examples/no-newline.txt || true
