"""The architecture rules in pyproject.toml ([tool.importlinter]) are part of the test suite.

They fail the tests if, for example, the application layer starts importing
psycopg, or the AniList adapter starts importing the PostgreSQL one.

import-linter runs in its own process: called in-process it reconfigures
Python's logging, which would break the log checks in other tests.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_import_contracts_are_kept():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from importlinter.cli import lint_imports; sys.exit(lint_imports(no_cache=True))",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
