#!/usr/bin/env python3
"""Gene-Migration ledger — one row per surface/story being migrated.

Modeled on the attractor `semport` fixture's ledger contract. Rows are TSV:

    <issue>\t<slug>\t<state>

The issue key uses the pipeline's path-safe STORY identifier grammar:
ASCII letters, digits, dot, underscore or hyphen; neither `.` nor `..` alone.
Labels may contain ordinary spaces and Unicode, but not TSV/line delimiters.

state ∈ {new, implemented, verified, acknowledged}
  new          — not yet ported
  implemented  — ported, validated (unit + forge), PR opened
  verified     — blind verifier (Loop 1) independently confirmed the behavior
  acknowledged — could not converge (or failed verification twice); human handoff

Commands (stdlib only, never raises for the pipeline's tool nodes):
  earliest              print "<key> <label>" of the first `new` row, or NONE
  earliest-implemented  print "<key> <label>" of the first `implemented` row, or NONE
                        (the blind verifier's queue — Loop 1)
                        The FIRST token is always the ledger KEY (col 0) — use it for
                        updates, artifact names, and result lines. The second token is
                        a label whose meaning varies by pipeline (HGT: target route;
                        GM: title slug) — never treat it as the key.
  update <issue> <st>   set a row's state
  stats                 counts by state
  sort                  rewrite file: new first, then implemented, then acknowledged
  add <issue> <slug>    append a new row (idempotent on issue)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Ledger file is overridable so one tool can serve several pipelines
# (e.g. the inventory ledger over surfaces.tsv and the migration ledger over backlog.tsv).
# Back-compatible: unset LEDGER_FILE keeps the original ledger.tsv sibling.
_LEDGER_ENV = os.environ.get("LEDGER_FILE")
LEDGER = Path(_LEDGER_ENV) if _LEDGER_ENV else Path(__file__).with_name("ledger.tsv")
ORDER = {"new": 0, "implemented": 1, "verified": 2, "acknowledged": 3}


def _field(value: str, name: str) -> None:
    if not value or value != value.strip() or any(
        char in value for char in "\t\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029\0"
    ):
        raise ValueError(f"invalid {name}: expected a nonempty single TSV field")
    if name == "key" and (value in {".", ".."} or re.fullmatch(r"[A-Za-z0-9._-]+", value) is None):
        raise ValueError("invalid key: expected a path-safe STORY identifier (A-Z, a-z, 0-9, dot, underscore or hyphen)")


def _rows() -> list[list[str]]:
    if not LEDGER.exists():
        return []
    out = []
    seen: set[str] = set()
    for number, line in enumerate(LEDGER.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError(f"row {number}: expected exactly three TSV fields")
        key, label, state = parts
        _field(key, "key")
        _field(label, "label")
        if state not in ORDER:
            raise ValueError(f"row {number}: invalid state {state!r}")
        if key in seen:
            raise ValueError(f"row {number}: duplicate key {key!r}")
        seen.add(key)
        out.append(parts)
    return out


def _write(rows: list[list[str]]) -> None:
    LEDGER.write_text("".join("\t".join(r) + "\n" for r in rows))


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "stats"
    rows = _rows()

    if cmd == "earliest":
        for issue, slug, state in rows:
            if state == "new":
                print(f"{issue} {slug}")
                return 0
        print("NONE")
        return 0

    if cmd == "earliest-implemented":
        for issue, slug, state in rows:
            if state == "implemented":
                print(f"{issue} {slug}")
                return 0
        print("NONE")
        return 0

    if cmd == "update" and len(argv) == 3:
        issue, state = argv[1], argv[2]
        if state not in ORDER:
            print(f"invalid state: {state}", file=sys.stderr)
            return 1
        matching = [row for row in rows if row[0] == issue]
        if not matching:
            print(f"unknown ledger key: {issue}", file=sys.stderr)
            return 1
        if any(row[2] == "verified" and state != "verified" for row in matching):
            print(f"verified is terminal: {issue}", file=sys.stderr)
            return 1
        for row in matching:
            row[2] = state
        _write(rows)
        print(f"{issue} -> {state}")
        return 0

    if cmd == "add" and len(argv) == 3:
        issue, slug = argv[1], argv[2]
        _field(issue, "key")
        _field(slug, "label")
        if not any(r[0] == issue for r in rows):
            rows.append([issue, slug, "new"])
            _write(rows)
        print(f"added {issue}")
        return 0

    if cmd == "sort":
        rows.sort(
            key=lambda r: (
                ORDER.get(r[2], 9),
                int(r[0]) if r[0].isdigit() else 0,
                r[0],
            )
        )
        _write(rows)
        print("sorted")
        return 0

    if cmd == "stats":
        counts: dict[str, int] = {}
        for _, _, state in rows:
            counts[state] = counts.get(state, 0) + 1
        print(" ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "empty")
        return 0

    print(f"unknown command: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        status = main(sys.argv[1:])
    except (OSError, ValueError) as exc:
        print(f"invalid ledger: {exc}", file=sys.stderr)
        status = 1
    raise SystemExit(status)
