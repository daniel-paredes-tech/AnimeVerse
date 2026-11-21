"""Guards for the migration rules (see docs/migrations.md).

1. Migrations are immutable: once committed, a migration file never changes.
   migrations.lock records each file's SHA-256; editing a recorded file
   fails this test. A new migration is added to the lock with:

       python tests/test_migrations.py

   (it only adds missing files; it never changes an existing line).

2. Expand/contract: a migration may only add things. Removing, renaming or
   tightening (DROP, RENAME, ALTER ... TYPE, SET NOT NULL, TRUNCATE, DELETE)
   is allowed only in a migration whose file name contains "contract",
   written after the code that needed the old shape is gone.

3. One straight line of numbered revisions: 0001, 0002, ... each pointing
   to the previous one, and a single head.
"""

import ast
import contextlib
import hashlib
import re
import sys
from pathlib import Path

VERSIONS = Path(__file__).resolve().parent.parent / "src/animeverse/infrastructure/postgres/migrations/versions"
LOCK_FILE = VERSIONS.parent / "migrations.lock"

DESTRUCTIVE = re.compile(
    r"\bDROP\s+(TABLE|COLUMN|INDEX|CONSTRAINT|SCHEMA|TYPE|VIEW|SEQUENCE)\b"
    r"|\bRENAME\b"
    r"|\bALTER\s+COLUMN\s+\w+\s+(SET\s+DATA\s+)?TYPE\b"
    r"|\bSET\s+NOT\s+NULL\b"
    r"|\bTRUNCATE\b"
    r"|\bDELETE\s+FROM\b",
    re.IGNORECASE,
)


def migration_files() -> list[Path]:
    return sorted(p for p in VERSIONS.glob("*.py") if p.name != "__init__.py")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_lock() -> dict[str, str]:
    entries = {}
    for line in LOCK_FILE.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            digest, name = line.split()
            entries[name] = digest
    return entries


def upgrade_source(path: Path) -> str:
    """The source code of the migration's upgrade() function."""
    source = path.read_text()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
            body = ast.get_source_segment(source, node) or ""
            # upgrade() usually runs a module-level SQL constant: include the constants it names.
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            constants = [
                ast.get_source_segment(source, n) or ""
                for n in ast.parse(source).body
                if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)
            ]
            return "\n".join([body, *constants])
    raise AssertionError(f"{path.name} has no upgrade() function")


def without_sql_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def test_committed_migrations_are_never_edited():
    lock = read_lock()
    edited = [name for name, digest in lock.items() if (VERSIONS / name).exists() and sha256(VERSIONS / name) != digest]
    deleted = [name for name in lock if not (VERSIONS / name).exists()]
    assert not edited, f"Applied migrations must never change; write a new migration instead. Edited: {edited}"
    assert not deleted, f"Applied migrations must never be deleted: {deleted}"


def test_every_migration_is_recorded_in_the_lock():
    missing = [p.name for p in migration_files() if p.name not in read_lock()]
    assert not missing, f"Record new migrations with `python tests/test_migrations.py`: {missing}"


def test_only_contract_migrations_remove_or_rename():
    offenders = [
        p.name
        for p in migration_files()
        if "contract" not in p.name and DESTRUCTIVE.search(without_sql_comments(upgrade_source(p)))
    ]
    assert not offenders, f"Destructive SQL outside a *_contract_* migration (see docs/migrations.md): {offenders}"


def test_revisions_form_one_numbered_line():
    previous = None
    for number, path in enumerate(migration_files(), start=1):
        expected = f"{number:04d}"
        assert path.name.startswith(f"{expected}_"), f"{path.name} should start with {expected}_"
        values = _module_constants(path)
        assert values.get("revision") == expected, f"{path.name}: revision should be {expected!r}"
        assert values.get("down_revision") == previous, f"{path.name}: down_revision should be {previous!r}"
        previous = expected


def _module_constants(path: Path) -> dict[str, object]:
    """Top-level `name = <literal>` assignments, e.g. revision and down_revision."""
    values: dict[str, object] = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            with contextlib.suppress(ValueError):  # not a literal (e.g. a call): not needed here
                values[node.targets[0].id] = ast.literal_eval(node.value)
    return values


def _add_missing_to_lock() -> None:
    lock = read_lock()
    new = [p for p in migration_files() if p.name not in lock]
    with LOCK_FILE.open("a") as f:
        for path in new:
            f.write(f"{sha256(path)}  {path.name}\n")
            print(f"recorded {path.name}")
    if not new:
        print("nothing to record")


if __name__ == "__main__":
    _add_missing_to_lock()
    sys.exit(0)
