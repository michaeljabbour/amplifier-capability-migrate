#!/usr/bin/env python3
"""Stage/stash project paths while retaining pipeline controls and user index data.

Path enumeration and literal NUL framing avoid Git's ignored-negative-pathspec
failure and filename quoting ambiguities. This is not a concurrent-writer lock.
"""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys


def git(*args: str, input: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "--literal-pathspecs", *args], input=input, capture_output=True)


def output(*args: str) -> bytes:
    result = git(*args)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or "Git inspection failed")
    return result.stdout


def names(raw: bytes) -> list[str]:
    return list(dict.fromkeys(os.fsdecode(item) for item in raw.split(b"\0") if item))


def control_nodes(root: Path, configured: list[str]) -> set[str]:
    controls: set[str] = set()
    expanded = list(configured)
    if len(configured) > 1 and configured[1]:
        ledger = Path(os.path.abspath(configured[1])).resolve()
        expanded.extend(str(ledger.with_name(name)) for name in ["git_controls.py", "validation_record.py"])
    for value in expanded:
        if not value:
            continue
        lexical = Path(os.path.abspath(value))
        # Canonicalize aliases leading INTO the repository (e.g. /var ->
        # /private/var) before following any link owned by the repository.
        candidates = [lexical]
        for length in range(1, len(lexical.parts) + 1):
            if Path(*lexical.parts[:length]).resolve() == root:
                candidates.append(root.joinpath(*lexical.parts[length:]))
                break
        # Keep an in-repository link itself, even when its referent is outside.
        candidates.extend([lexical.parent.resolve() / lexical.name, lexical.resolve()])
        for candidate in candidates:
            if not candidate.is_relative_to(root):
                continue
            relative = candidate.relative_to(root)
            current = root
            for index, part in enumerate(relative.parts, 1):
                current /= part
                if current.is_symlink():
                    relative = Path(*relative.parts[:index])
                    break
            controls.add(relative.as_posix())
    return controls


def is_control(name: str, controls: set[str]) -> bool:
    parts = name.split("/")
    return (any(part in {".ai", "__pycache__"} for part in parts)
            or name.endswith(".pyc") or parts[0] == "inventory"
            or any(name == control or name.startswith(control + "/") for control in controls))


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] not in {"stage", "stash"}:
        print("usage: git_controls.py stage|stash BACKLOG LEDGER_TOOL", file=sys.stderr)
        return 2
    try:
        root = Path.cwd().resolve()
        top = Path(os.fsdecode(output("rev-parse", "--show-toplevel")).rstrip("\n")).resolve()
        if top != root:
            raise ValueError("target must be the repository root")
        controls = control_nodes(root, argv[1:])
        if argv[0] == "stage" and any(is_control(name, controls) for name in names(output("diff", "--cached", "--no-renames", "--name-only", "-z"))):
            raise ValueError("control metadata is already staged; review index without auto-unstaging")
        paths = [name for name in names(output("ls-files", "-z", "--cached", "--others", "--exclude-standard")) if not is_control(name, controls)]
        if not paths:
            return 0
        payload = b"".join(os.fsencode(name) + b"\0" for name in paths)
        command = ["add", "-A"] if argv[0] == "stage" else ["stash", "push", "-q", "--include-untracked"]
        result = git(*command, "--pathspec-from-file=-", "--pathspec-file-nul", input=payload)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace").strip() or "Git mutation failed")
        if argv[0] == "stage" and any(is_control(name, controls) for name in names(output("diff", "--cached", "--no-renames", "--name-only", "-z"))):
            raise ValueError("control metadata staged unexpectedly; stopped without commit/unstaging")
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Git control boundary: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
