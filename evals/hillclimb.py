#!/usr/bin/env python3
"""Run monitor for the Gene-Migration attractor (ratchet over backlog snapshots).

SCOPE: inner run monitor. Rows only move forward, so this cannot rank technique
variants (v1 vs v2) — see docs/EVALUATION.md for the external objective function.

DEFAULT (builder loop): landed_frac (implemented+verified) non-decreasing; no landed
row un-completes; sequence lookahead <= --max-lookahead (default 8).

--verifier (Loop 1 in play): the blind verifier may legally reopen an implemented
row (implemented -> new). Asserts verified_frac non-decreasing and that no row ever
LEAVES `verified` (terminal); reopens are reported, not failed; lookahead still
checked.

Usage:
    python3 evals/hillclimb.py [--verifier] [--max-lookahead N] <snap0.tsv> ...
    python3 evals/hillclimb.py --fixture | --fixture-verify | --self-test
"""
from __future__ import annotations

import sys
from pathlib import Path

from fitness import fitness, read_rows, validate_rows

HERE = Path(__file__).parent
FIXTURE = sorted((HERE / "fixtures" / "run").glob("*.tsv"))
FIXTURE_VERIFY = sorted((HERE / "fixtures" / "verify").glob("*.tsv"))
DEFAULT_MAX_LOOKAHEAD = 8


def _bar(frac: float, width: int = 24) -> str:
    n = round(frac * width)
    return "█" * n + "·" * (width - n)


def check(series, verifier=False, max_lookahead=DEFAULT_MAX_LOOKAHEAD):
    notes: list[str] = []
    if not series:
        return False, ["invalid run: no snapshots supplied"]
    ok = True
    prev_f = None
    prev_state: dict[str, str] = {}
    prev_label: dict[str, str] = {}
    for i, rows in enumerate(series):
        try:
            validate_rows(rows)
        except ValueError as exc:
            return False, notes + [f"    ✗ invalid snapshot {i}: {exc}"]
        f = fitness(rows)
        notes.append(
            f"  step {i}: {_bar(f['verified_frac'] if verifier else f['landed_frac'])} "
            f"impl={f['implemented']} ver={f['verified']}/{f['total']} "
            f"landed={f['landed_frac']:.2f} verified={f['verified_frac']:.2f} lookahead={f['lookahead']}"
        )
        state = {r[0]: r[2] for r in rows}
        label = {r[0]: r[1] for r in rows}
        for key in sorted(prev_state.keys() - state.keys()):
            ok = False
            notes.append(f"    ✗ REGRESSION: story {key!r} disappeared from queue")
        for key in sorted(prev_label.keys() & label.keys()):
            if prev_label[key] != label[key]:
                ok = False
                notes.append(f"    ✗ REGRESSION: story {key!r} changed label")
        if prev_f is not None:
            key = "verified_frac" if verifier else "landed_frac"
            if f[key] < prev_f[key] - 1e-9:
                ok = False
                notes.append(f"    ✗ REGRESSION: {key} fell {prev_f[key]:.2f} -> {f[key]:.2f}")
        if f["lookahead"] > max_lookahead:
            ok = False
            notes.append(f"    ✗ SEQUENCE: lookahead {f['lookahead']} > {max_lookahead}")
        for sid, st in prev_state.items():
            now = state.get(sid)
            if st == "verified" and now != "verified":
                ok = False
                notes.append(f"    ✗ REGRESSION: '{sid}' left terminal verified -> {now}")
            elif not verifier and st == "implemented" and now in ("new", "acknowledged"):
                ok = False
                notes.append(f"    ✗ REGRESSION: '{sid}' un-completed ({st} -> {now})")
            elif verifier and st == "implemented" and now == "new":
                notes.append(f"    ↺ reopened by verifier: '{sid}'")
        prev_f, prev_state, prev_label = f, state, label
    return ok, notes


def _self_test() -> int:
    ok_all = True
    good = [
        [("s1", "core", "new"), ("s2", "loop", "new")],
        [("s1", "core", "implemented"), ("s2", "loop", "new")],
        [("s1", "core", "implemented"), ("s2", "loop", "implemented")],
    ]
    bad = [
        [("s1", "core", "implemented"), ("s2", "loop", "implemented")],
        [("s1", "core", "new"), ("s2", "loop", "implemented")],
    ]
    g, _ = check(good)
    b, _ = check(bad)
    print("builder mode: climbing:", g, "| un-complete rejected:", not b)
    ok_all &= g and not b
    v_good = [
        [("s1", "core", "implemented"), ("s2", "loop", "implemented")],
        [("s1", "core", "verified"), ("s2", "loop", "implemented")],
        [("s1", "core", "verified"), ("s2", "loop", "new")],   # legal reopen
        [("s1", "core", "verified"), ("s2", "loop", "implemented")],
        [("s1", "core", "verified"), ("s2", "loop", "verified")],
    ]
    v_bad = [
        [("s1", "core", "verified"), ("s2", "loop", "implemented")],
        [("s1", "core", "new"), ("s2", "loop", "implemented")],  # left verified
    ]
    vg, _ = check(v_good, verifier=True)
    vb, _ = check(v_bad, verifier=True)
    print("verifier mode: reopen tolerated:", vg, "| verified-exit rejected:", not vb)
    ok_all &= vg and not vb
    print("SELF-TEST", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


def main(argv: list[str]) -> int:
    verifier = False
    max_lookahead = DEFAULT_MAX_LOOKAHEAD
    if argv[:1] == ["--verifier"]:
        verifier = True
        argv = argv[1:]
    if argv[:1] == ["--max-lookahead"] and len(argv) >= 2:
        max_lookahead = int(argv[1])
        argv = argv[2:]
    if argv == ["--self-test"]:
        return _self_test()
    if argv == ["--fixture-verify"]:
        paths, verifier = [str(p) for p in FIXTURE_VERIFY], True
    elif argv == ["--fixture"] or not argv:
        paths = [str(p) for p in FIXTURE]
    else:
        paths = argv
    if not paths:
        print("no fixtures found", file=sys.stderr)
        return 2
    print(f"GM hill-climb ({'verifier' if verifier else 'builder'} mode) over {len(paths)} snapshot(s):")
    try:
        series = [read_rows(p) for p in paths]
    except (OSError, ValueError) as exc:
        print(f"invalid backlog: {exc}", file=sys.stderr)
        return 2
    ok, notes = check(series, verifier, max_lookahead)
    print("\n".join(notes))
    print("VERDICT:", "CLIMBING ✓" if ok else "REGRESSION ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
