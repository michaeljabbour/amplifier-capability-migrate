# Evaluating GM — three loops, honestly scoped

Implementation description reviewed October 29, 2026. No new live migration run is reported here.

Grounded in reviewer feedback (from the author of the reality-check / DTU /
evaluation bundles) that identified two real gaps. The native outer verifier is
now implemented; the technique comparison remains unfinished. This document
distinguishes that implementation from the evidence that a particular run used it.

1. **The pipeline authors the acceptance artifacts it is graded against.**
   `PlanPort` writes the forge probe, `Implement` writes the unit tests — the
   same flow that must pass them. The current `AnalyzeFailure` node in
   [`pipelines/migrate.dot`](../pipelines/migrate.dot) may propose a story-card
   amendment, but explicitly forbids editing the story cards from the build loop.
   The gate *execution* is deterministic and per-node contexts are fresh
   (`truncate` fidelity), but deterministic ≠ independent: the gate's
   *definition* still comes from inside the loop.
2. **`evals/hillclimb.py` is near-tautological as a technique signal.** The
   builder protocol intends forward state transitions, so "up and to the right"
   within its run is close to guaranteed by construction. The separate verifier
   may reopen work. Neither curve can say GM-v2 beats GM-v1.

This doc scopes what exists, what is connected, and which measurements remain.

## Loop 0 — what exists: the run monitor (inner)

`evals/fitness.py` + `hillclimb.py`: a ratchet over backlog snapshots. Honest
scope: detects a stalled, regressing, or sequence-violating **run** (and a
technique that gives up scores 0 via `acknowledged`), with quality baked in
only to the extent the in-loop gates are trustworthy. Keep it for what it is —
run health + Goodhart tripwires — not an objective function.

## Loop 1 — outer verification: grader independence (reality-check, adapted)

[amplifier-bundle-reality-check](https://github.com/microsoft/amplifier-bundle-reality-check)'s
shape: an `intent-analyzer` derives structured acceptance tests from the user's
intent (not from the builder); validators (terminal/browser/generic testers)
execute them against the software deployed in a DTU; a gap report follows.
The grader's criteria never come from the build loop.

Our adaptation exploits GM's 1:1 advantage — the ground truth is an
**executable app**, not a conversation:

- A **blind verifier** session derives its own acceptance from the SOURCE app
  (boots it via forge, observes real behavior) — it never reads `.ai/`, the
  story cards, or the builder's tests/probe — then validates the TARGET in a
  DTU and emits `verified | rejected(findings)` per story.
- `rejected` reopens the row (`implemented → new`, findings attached), bounded
  once, then `acknowledged` with the verifier's findings for a human.
- The ledger supports a terminal state **`verified`**; the eval's protected scalar
  becomes `verified_frac` (`implemented_frac` becomes intermediate).
- The fix loop may **propose** a story-card amendment; only the verifier or a
  human may accept it after checking the source behavior. This moves rubric
  authority outside the builder protocol; instruction-level separation is not
  proof that a live session respected the boundary.

### Implemented native surface

| Source | What it implements |
| --- | --- |
| [`pipelines/verify.dot`](../pipelines/verify.dot) | A separate queue: `CheckQueue` → `SelectRow` → `DeriveChecks` → `RunChecks`, then `MarkVerified` or `RecordFindings` / `ReopenGate`. |
| [`agents/gm-verifier.md`](../agents/gm-verifier.md) | The verifier role, source-observation procedure and explicit prohibitions on reading builder artifacts, story cards and target tests. |
| [`pipelines/ledger.py`](../pipelines/ledger.py) | The `earliest-implemented` queue and storage of `new`, `implemented`, `verified` and `acknowledged` states. |
| [`evals/hillclimb.py`](../evals/hillclimb.py) | Verifier-mode monitoring: a bounded reopen is allowed; leaving the terminal `verified` state is rejected by the monitor. The ledger helper itself is not an access-control or transition-policy boundary. |
| [`context/gm-runbook.md`](../context/gm-runbook.md) | The explicit run order: build loop to quiescence, then verifier loop to quiescence, then rebuild/reverify rejected work within the declared bounds. |

This is a **separate graph**, not an automatic node inserted into the build graph.
The retained [`gm-pipeline` launcher](../bundles/gm-pipeline.yaml) selects
`pipelines/migrate.dot`; a caller must deliberately run `pipelines/verify.dot`
with its source, target, ledger and Forge parameters. Installing the portable
skill or completing the build graph does not by itself run blind verification.

The verifier agent's policy permits adjudicating amendment proposals after its
own source observation. The graph does not contain a separate automatic
amendment-adjudication node; do not infer that each run reviewed those proposals.

The [October 28 validation record](VALIDATION.md) establishes graph parsing and
ledger/monitor fixture behavior. It does not establish source/target parity,
verifier blindness in a live session, or a completed migration. The historical
DTU claim below is separate from those current local checks.

## Loop 2 — the technique objective function: frozen answer key (outermost)

To hillclimb the **technique**, the number must come from outside the loop:

- **Scenario:** a real port that already happened. Freeze the repo at the
  commit *before* the port. Run GM on that state — the flow never sees the
  real port.
- **Grade:** run the real port's *behavioral* test suite against what GM
  produced, plus parity probes. Score = % answer-key checks passed (+ surface
  coverage as secondary).
- **Climb:** GM-v1 vs GM-v2 on the identical frozen scenario, K≥3 repeats per
  variant — our own two inventory runs of the same toy produced 3-story and
  6-story backlogs, so single-run numbers are noise. Then "moving the probe
  earlier bought 15 points" is a sentence with meaning.

**Worked candidate (verified from git history):** `openai/codex` TypeScript/Ink
→ Rust. At tag `rust-v0.0.2504301219` both `codex-cli/` (TypeScript — `ink`,
`react`, `ink-testing-library` in its package.json) and `codex-rs/` coexist in
the tree; today's `codex-rs` carries `cli/tests/` suites and e2e benches
(black-box candidates). Pilot on a **scoped slice** (e.g. `exec` +
`apply-patch`), not the whole app.

Threats, named up front:
- **Contamination.** codex is in every frontier model's training data; the
  model may recall the real Rust port. Mitigations: grade only on behavioral
  tests; treat v1-vs-v2 *deltas* on the same task as the primary number
  (recall inflates both arms); prefer obscure or private answer keys for
  trustworthy absolutes.
- **Test coupling.** Most cargo unit tests are structure-coupled and will not
  run against an independently-shaped port. Use the CLI/integration subset;
  where thin, derive black-box checks *from* the answer key's tests rather
  than running them verbatim.

## Roadmap

1. IMPLEMENTED — `verify.dot`, the blind-verifier agent, ledger queue and monitor
   are present at the linked paths above. The original project notes report a
   historical DTU check (two positive cases, one sabotage rejected, blindness
   audit clean); that report is not a fresh live run or independent reproduction
   in the October 28 packaging validation.
2. ✅ PILOT DELIVERED — `benchmarks/codex-apply-patch/`: grader calibrated 21/21
   vs the real codex-rs; GM-v1 scored externally (headline 13/16; see
   [`benchmarks/codex-apply-patch/RESULTS.md`](../benchmarks/codex-apply-patch/RESULTS.md) incl. the design defects to fix
   before any v1-vs-v2 comparison).
3. NEXT (not started): fix the pilot's Loop-2 defects, then v1-vs-v2 with K≥3 —
   only then tune the technique, with Loop 2 as arbiter.
