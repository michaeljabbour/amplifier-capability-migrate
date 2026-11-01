#!/usr/bin/env python3
"""Write the current validation attempt/stage record, without interpreting logs."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import sys
import tempfile

STAGES = {"unit": ("unit.log",), "forge_doctor": ("forge-doctor.log",),
          "forge": ("forge-doctor.log", "forge.log")}
RESULTS = {"running", "pass", "fail", "blocked"}


def regular(path: Path, directory: bool = False) -> None:
    if path.is_symlink():
        raise ValueError("symlinked validation metadata")
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError("missing or non-regular validation metadata")


def write_record(story: str, attempt: int, stage: str, result: str, logs: list[str]) -> None:
    if story in {".", ".."} or re.fullmatch(r"[A-Za-z0-9._-]+", story) is None:
        raise ValueError("invalid STORY")
    if not 1 <= attempt <= 3 or stage not in STAGES or result not in RESULTS:
        raise ValueError("invalid attempt/stage/result")
    expected = [f".ai/gm_logs/{story}/{name}" for name in STAGES[stage]]
    if logs != expected:
        raise ValueError("log list does not match the current validation stage")
    for directory in [Path(".ai"), Path(".ai/gm_logs"), Path(".ai/gm_logs") / story]:
        regular(directory, directory=True)
    for name in logs:
        regular(Path(name))
    target = Path(".ai/gm_validation.json")
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError("invalid validation record destination")
    payload = {"schema_version": 1, "story": story, "attempt": attempt,
               "stage": stage, "result": result, "logs": logs}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                prefix=".gm-validation-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, indent=2)
            stream.write("\n")
            stream.flush()
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    if len(argv) < 6 or argv[0] != "write":
        print("usage: validation_record.py write STORY ATTEMPT STAGE RESULT LOG...", file=sys.stderr)
        return 2
    try:
        write_record(argv[1], int(argv[2]), argv[3], argv[4], argv[5:])
    except (OSError, ValueError) as exc:
        print(f"invalid validation record: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
