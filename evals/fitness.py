#!/usr/bin/env python3
"""Fitness function for the Gene-Migration attractor — run-monitor scalars.

WHAT IS BEING MEASURED: the migration drives every backlog story to a green-gated PR
(`implemented`) IN DEPENDENCY ORDER, and Loop 1 (the blind verifier,
pipelines/verify.dot) then drives it to `verified` — independently confirmed against
the SOURCE app's real behavior. `implemented` bakes in the builder's own gates;
`verified` bakes in an INDEPENDENT rubric. `acknowledged` earns nothing.

Backlog row: <story-id>\t<title-slug>\t<state>  state in {new, implemented, verified, acknowledged}

Usage:
    python3 evals/fitness.py <backlog.tsv>
"""
from __future__ import annotations

import sys
import re
from pathlib import Path


STATES = frozenset({"new", "implemented", "verified", "acknowledged"})


def validate_rows(rows: list[tuple[str, str, str]]) -> None:
    """A malformed queue is invalid evidence, not partial progress."""
    seen: set[str] = set()
    for number, row in enumerate(rows, 1):
        if not isinstance(row, (tuple, list)) or len(row) != 3:
            raise ValueError(f"row {number}: expected exactly three fields")
        key, label, state = row
        if not all(isinstance(value, str) and value.strip() and value == value.strip()
                   and not any(char in value for char in "\t\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029\0")
                   for value in row):
            raise ValueError(f"row {number}: key, label and state must be nonempty strings")
        if key in {".", ".."} or re.fullmatch(r"[A-Za-z0-9._-]+", key) is None:
            raise ValueError(f"row {number}: key cannot address a path-safe pipeline STORY")
        if state not in STATES:
            raise ValueError(f"row {number}: invalid state {state!r}")
        if key in seen:
            raise ValueError(f"row {number}: duplicate key {key!r}")
        seen.add(key)


def read_rows(path: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError(f"{path}:{number}: expected exactly three TSV fields")
        rows.append((parts[0], parts[1], parts[2]))
    validate_rows(rows)
    return rows


def fitness(rows: list[tuple[str, str, str]]) -> dict:
    validate_rows(rows)
    total = len(rows)
    denom = total or 1
    impl = sum(1 for r in rows if r[2] == "implemented")
    ver = sum(1 for r in rows if r[2] == "verified")
    ack = sum(1 for r in rows if r[2] == "acknowledged")
    new = sum(1 for r in rows if r[2] == "new")
    # sequence lookahead: an "unfinished" row is new OR reopened; landed = implemented|verified.
    landed_states = ("implemented", "verified")
    first_unfinished = next((i for i, r in enumerate(rows) if r[2] == "new"), None)
    last_landed = next((i for i in range(total - 1, -1, -1) if rows[i][2] in landed_states), None)
    lookahead = 0
    if first_unfinished is not None and last_landed is not None and last_landed > first_unfinished:
        lookahead = last_landed - first_unfinished
    return {
        "total": total,
        "implemented": impl,
        "verified": ver,
        "acknowledged": ack,
        "new": new,
        "implemented_frac": round(impl / denom, 4),
        "verified_frac": round(ver / denom, 4),  # Loop-1 PROTECTED scalar
        "landed_frac": round((impl + ver) / denom, 4),  # legacy PROTECTED scalar
        "resolved_frac": round((impl + ver + ack) / denom, 4),
        "lookahead": lookahead,  # WATCH — sequence adherence (small is healthy)
        "score": round((impl + ver) / denom, 4),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: fitness.py <backlog.tsv>", file=sys.stderr)
        return 2
    try:
        result = fitness(read_rows(argv[1]))
    except (OSError, ValueError) as exc:
        print(f"invalid backlog: {exc}", file=sys.stderr)
        return 2
    for k, v in result.items():
        print(f"{k}\t{v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
