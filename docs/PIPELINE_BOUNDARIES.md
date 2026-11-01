# Pipeline metadata and failure boundaries

The inventory phase accepts an existing target directory, including a new empty
directory without Git. Its Preflight gate validates `.ai` and `inventory` output
boundaries before EnumerateSurfaces runs. ValidateSurface reads the selected
`SURFACE` as data before derivation. Migration requires the actual target Git
repository root. Missing configured input ledgers are blocked; an existing valid
empty ledger is an empty queue. The standalone ledger `add` command may still
create a new ledger, including the inventory's initial surface/backlog files.

Main migration metadata is under `.ai`. State, retry counts, plans, probes,
blocked handoffs and per-story log paths refuse direct symbolic links and
non-regular files or directory ancestors before deterministic reads/writes.
`STORY` and `SURFACE` are parsed as data using the documented path-safe key
grammar; empty or duplicate assignments are invalid. Generated CI/probe scripts
remain executable program input selected by the migration workflow; these
checks do not sandbox arbitrary code or establish adversarial race safety.

Main logs have moved from shared `/tmp/gm_*` files to target-owned paths:

- `.ai/gm_logs/<STORY>/unit.log`
- `.ai/gm_logs/<STORY>/forge-doctor.log`
- `.ai/gm_logs/<STORY>/forge.log`
- `.ai/gm_logs/<STORY>/pr.log`

Analysis prompts read these paths. Verifier logs stay at
`.ai/verify_logs/<STORY>.log` and `<STORY>-doctor.log`. Existing installation,
module IDs, story order, normal pass/fail, retry/giveup and next token names remain. The retry counter now enforces three total attempts (two retries), matching PRINCIPLES.md; the previous controller accidentally allowed a fourth attempt.
Missing or malformed prerequisites use an explicit `blocked` edge with adapter
exit status0 so an engine cannot reuse a stale last stdout line. A completed
unit/probe check with a nonzero result still emits `fail`.

## Reopen write errors

The verifier must persist its once-only reopen marker before advancing the
ledger to `new`. If marker creation fails, it emits `blocked` without attempting
the ledger update. If the update fails, it removes the newly created marker when
possible and emits `blocked`. If cleanup also fails, it remains blocked with a
conservatively consumed marker for human inspection; it never emits `next`.
Existing ratchet markers are preserved on later failures. No multi-file atomic
transaction, concurrent-writer locking or crash-consistency guarantee is made.
A crash after intent persistence may conservatively consume the reopen allowance;
operators should inspect the ledger and marker before manually resuming.

The offline command fixtures use temporary repositories and authored Git/gh,
Forge and CI stubs. They test routing and metadata integrity, not a successful
model-directed migration. AGENTS.md's real scratch inventory/migration/Forge
acceptance gate remains separate.

## Git staging and control inputs

Git stash/add enumerate Git's tracked and nonignored untracked paths with NUL
framing. The Git-control helper filters root/nested `.ai`, `__pycache__`, `.pyc`,
the root `inventory/` artifacts, and configured BACKLOG/LEDGER_TOOL controls inside
the target. It also retains the actual sibling controller helpers. Lexical
in-target symlink nodes stay excluded even when their referents are outside;
normal external configured paths remain valid. Only eligible literal project
paths are supplied to Git through NUL pathspec input. This avoids negative
pathspec failures on ignored control parents and quoting/magic ambiguity in
filenames. The installed Git must support `--pathspec-from-file` and
`--pathspec-file-nul`; no ignore rules are changed or force flags used.

Ordinary project edits, new files and tracked deletions still follow the existing
per-story workflow. Earlier stash entries and the user's index snapshot are
preserved. A pre-staged control/metadata change blocks Commit instead of being
silently unstaged or included. Review and commit such control changes separately
when appropriate. Queue progress stays local across story branches and main
checkouts. The native migration phase expects an existing main branch/commit;
it does not reset or initialize a user's repository implicitly.

## Current failure evidence

`.ai/gm_validation.json` records the current story, attempt (1–3), stage, result
and exact validation logs. Its helper replaces the JSON record atomically and
refuses malformed paths/fields or symlinked destinations. A new unit attempt
marks skipped Forge/doctor logs UNRUN; a failing doctor excludes the probe log
from the current record. AnalyzeFailure reads this record first and uses only
its listed validation logs. Older implementation history is not current gate
output. A record-write failure blocks before reporting success or continuing.

## Existing-branch recovery is a manual gate

A verifier can legitimately reopen a row to `new` while `gm/<story>` already
exists. BranchSetup intentionally blocks before stash/checkout on that branch;
there is no automatic rebuild in this case. The original branch/commits, PR and
other workers' dirty files or worktrees must remain intact.

Before authorizing recovery, inspect the exact branch SHA, clean/dirty index and
working tree, registered worktrees and active worker ownership, and the matching
PR's current head/state/checks. Choose explicitly whether to continue work on the
owned branch after those checks, or prepare a separately named recovery branch
from an agreed SHA with its PR relationship recorded. That decision requires an
explicit resume/recovery design; current graphs provide neither automatic path.
Do not delete worktrees or reset/reuse/rename branches to make the loop pass.
Native fixtures confirm the reopened row remains `new`, BranchSetup emits
`blocked`, and the existing commit plus an authored worker draft are preserved.
