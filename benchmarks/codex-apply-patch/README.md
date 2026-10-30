# codex-apply-patch — frozen answer-key benchmark (Loop 2 pilot)

The **technique-level objective function** for GM (see `../../docs/EVALUATION.md`
Loop 2): a real historical port graded from OUTSIDE the loop.

## Scenario

`openai/codex` was ported TypeScript→Rust. Frozen at tag `rust-v0.0.2504301219`:

- **Source (shown to the flow):** the pre-port TypeScript apply-patch slice —
  `upstream/ts/` (`apply-patch.ts`, `parse-apply-patch.ts` + their TS tests,
  Apache-2.0, © OpenAI). The flow ports this to a Rust crate.
- **Answer key (NEVER shown to the flow):** the real Rust port — `upstream/rs/`
  (`codex-rs/apply-patch` at the same tag). Used only to harvest grader cases
  and to calibrate.

## The fixed CLI contract (the 1:1 adaptation)

Candidate ports must expose a binary that: reads the full patch envelope
(`*** Begin Patch … *** End Patch`) from **stdin**, applies changes relative to
**cwd**, exits **0 iff the patch applied**, non-zero otherwise. stdout/stderr are
not graded. The same contract wraps the real implementation for calibration
(`calibration/` — a thin shim over `codex_apply_patch::apply_patch`).

## Execution boundary

The caller-selected `--bin` is executable code with the grader user's normal OS
permissions. Use a trusted candidate, or run the entire grader in an external OS
sandbox before selecting an untrusted program. The minimal child environment and
case-local HOME/tmp prevent accidental host credential/config inheritance; they
do not prevent absolute filesystem access, network access or child processes.
No claim that a candidate is sandboxed follows from its temporary working folder.

Fixture seed and expected paths must be relative POSIX names without traversal or
Windows drive syntax. The grader validates them before execution, seeds through
no-follow directory descriptors, and never follows snapshot symlinks/hardlinks or
reads special files. Unsafe/unreadable entries fail a checked tree. These guards
require supported Unix descriptor operations (verified locally on macOS arm64);
unsupported hosts fail closed. Frozen case content and scoring expectations are
unchanged.

## Grading

`cases/cases.json` — 21 black-box cases harvested from the answer key's own test
suite (mapping + adaptations in `cases/HARVEST_NOTES.md`):
11 success-path · 5 parse-invalid (exit≠0) · 5 `quirk_*` cases pinning the real
implementation's **discovered** behavior: runtime failures (context mismatch,
nonexistent file) exit **0** silently, and application is **non-atomic across
hunks**. Verified empirically before encoding — the cases encode what the answer
key DOES, not what seems ideal.

```sh
cd calibration && cargo build --release && cd ..
python3 grade.py --bin calibration/target/release/codex-apply-patch-shim   # calibration: 21/21
python3 grade.py --bin <candidate-binary> --json results.json              # grade a port
```

**Calibration result: `SCORE: 21/21`** against the real codex-rs implementation.

## Scoring nuance — report the breakdown, not just the total

The `quirk_*` cases measure fidelity to the ANSWER KEY, whose edge behavior may
itself diverge from the TS source (the real port changed/embraced these
semantics). A flow that faithfully ports TS behavior can legitimately fail
quirk cases while being a good migration of the SOURCE. Always report:
success-path score, invalid-handling score, and quirk score separately —
the headline number is the success-path + invalid score; quirks are a fidelity
signal about WHICH implementation the port resembles.

## Threats (named, not glossed)

- **Contamination:** codex is in frontier-model training data; a model may
  recall codex-rs. Use v1-vs-v2 DELTAS on this same frozen task as the primary
  number (recall inflates both arms); prefer obscure/private answer keys for
  trustworthy absolutes. Residual: this repo vendors the answer key under
  `upstream/rs/` — scenario materialization must copy ONLY `upstream/ts/` into
  the environment the flow can reach.
- **Contract fixture:** the CLI contract is ours, not codex's — both the real
  implementation (via the shim) and candidates are graded through the identical
  contract, so the comparison stays fair.

## Running the benchmark (pilot shape)

1. Materialize the scenario: source repo = `upstream/ts/` files + a README
   stating the contract; target = empty Rust repo (`TARGET_KIND=new:rust`).
2. Run GM (inventory → migrate to quiescence) in an isolated DTU. The flow never
   sees `upstream/rs/` or `cases/`.
3. Build the produced crate; `python3 grade.py --bin <produced-binary>`.
4. Compare GM-v1 vs GM-v2 on THIS same frozen scenario, K≥3 repeats per variant
   (single-run inventories are nondeterministic — observed 3-story vs 6-story
   backlogs from an identical toy source).
