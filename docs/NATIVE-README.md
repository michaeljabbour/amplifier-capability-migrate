> Original native guide, preserved at source commit `a20f50716d4bd07053a04b84fe5c50d6eee547ef`. Install locations, model names, service availability, and claims below are historical and must be verified before use. Current portable installation is in INSTALL.md.

# amplifier-bundle-genemigration

**GM — the Gene-Migration attractor.** A self-contained Amplifier bundle that
migrates a whole application from **one language to another**, driven by a
reverse-engineered **inventory** of user stories + acceptance criteria, properly
sequenced so the attractor rebuilds the app feature-by-feature — each feature
verified against its own derived acceptance criteria + a real-terminal
[forge](https://github.com/michaeljabbour/amplifier-skill-forge) check.

Sibling to [`amplifier-bundle-genetransfer`](https://github.com/michaeljabbour/amplifier-bundle-genetransfer)
(HGT): where HGT *cherry-picks capabilities* from a donor into existing hosts, GM
*rebuilds a whole app* in a new language. Same engine, different job.

## Two phases

1. **Inventory (reverse requirements engineering).** Study the source app — its code
   AND its live behavior via forge — and emit dependency-**sequenced** user stories
   with testable Given/When/Then acceptance criteria. The inventory is the assist:
   it's the spec and the migration order. (`gm-inventory` · `pipelines/inventory.dot`.)
2. **Migration (the attractor loop).** Rebuild the app story-by-story in sequence,
   each story implemented idiomatically in the target language, gated by its
   acceptance criteria (as target tests) + a forge boot of the migrated app, one PR
   per story. (`gm-orchestrator` · `pipelines/migrate.dot`.)

## Knobs

| Knob | What |
|---|---|
| **source** | `SOURCE_PATH` + `SOURCE_KIND` — the app being migrated (language A). Read + observe only. |
| **target** | `TARGET_PATH` + `TARGET_KIND` (`python`/`rust`/`new:<lang>`) — the migration home (language B). May be a **new/empty repo**; story #1 scaffolds its CI. |
| **inventory** | `<target>/inventory/` — the reverse-engineered plan, committed to the target repo as the living migration doc. |

## What makes it distinct

- **Reverse-engineered, sequenced spec.** Robust user stories + acceptance criteria,
  ordered by dependency — the sequence IS the migration plan.
- **Behavior fidelity, idiomatic rebuild.** Study the source deeply; re-implement in
  the target's own idioms; never transliterate. Acceptance criteria are the oracle.
- **Living inventory.** A gate failure that exposes a wrong criterion amends the
  story card — the spec is corrected, never force-greened.
- **Forge-woven QA + gate == CI**, same as HGT.

## Usage

**1. Install and activate**

```sh
amplifier bundle add git+https://github.com/michaeljabbour/amplifier-bundle-genemigration@main
amplifier bundle use gm            # /gm mode + gm-inventory / gm-orchestrator / gm-expert
```

**2. Define the knobs** (see `examples/newtui-to-rust/` for a filled-in instance):

```sh
export SOURCE_PATH=/abs/path/to/source-app   SOURCE_KIND=python   # read+observe only
export TARGET_PATH=/abs/path/to/target-repo  TARGET_KIND=rust     # may be new/empty
export FORGE_TOOL=~/.claude/skills/amplifier-skill-forge/tools/forge.py
export LEDGER_TOOL=/abs/path/to/this-bundle/pipelines/ledger.py
export SURFACES=$TARGET_PATH/inventory/surfaces.tsv
export BACKLOG=$TARGET_PATH/inventory/backlog.tsv
```

**3. Phase 1 — build the inventory.** `/gm`, then delegate to `gm-inventory` (or run
`pipelines/inventory.dot`): it enumerates the source's surfaces, derives user
stories + Given/When/Then acceptance per surface (observing the REAL app via forge),
and writes the dependency-sequenced backlog into `$TARGET_PATH/inventory/`.

**4. Review the backlog** — read `inventory/README.md` + a sample of story cards;
fix vague acceptance now, not mid-migration. The backlog's file order is the plan.

**5. Phase 2 — migrate.** Delegate to `gm-orchestrator` (or run
`pipelines/migrate.dot`): stories rebuild in sequence, idiomatic in the target
language, each gated by its acceptance tests + a forge boot of the migrated app,
one PR per story on `gm/<story>`. Bounded ≤3 attempts, then `acknowledged` + a
handoff file under `.ai/gm_blocked/`.

**6. Monitor & finish** — the backlog is the source of truth:
`LEDGER_FILE=$BACKLOG python3 pipelines/ledger.py stats`. Done = no `new` rows.
(run_pipeline engine alternative: `bundles/gm-interactive.yaml`; headless:
`bundles/gm-pipeline.yaml` with the env vars exported, launched from the repo root.
See `context/gm-runbook.md`.)

## Evaluation (hill-climbing)

The bundle ships a simple hill-climbing eval (`evals/`): fitness =
`implemented_frac` over the backlog (quality is a precondition — only stories whose
acceptance tests + forge check passed count), with a **ratchet check** — fitness
never falls, no story un-completes — plus a GM-specific **sequence check**
(lookahead past the earliest unfinished story stays within the parallel-lane cap;
leapfrogging the plan fails).

```sh
python3 evals/hillclimb.py --self-test    # prove the detector works
python3 evals/hillclimb.py --fixture      # demo curve
python3 evals/hillclimb.py snap0.tsv snap1.tsv …   # score a real run
```

See `evals/README.md` for what is measured and why. **Loop 1 is now built:**
`pipelines/verify.dot` + the blind `gm-verifier` agent drive `implemented`
rows to the terminal `verified` state against independently-derived checks
(monitor with `evals/hillclimb.py --verifier`); `docs/EVALUATION.md` holds the
full three-loop design.

## Validation (DTU reality check)

Both phases have been proven end-to-end in an isolated Digital Twin Universe
(bundle v0.1.1, 2026-07-28), from a pristine empty target:

- **Inventory** — root session `5cb0946f…` delegated to the real `gm-inventory`
  agent (child session `…_gm:gm-inventory`, `parent_id == root` — genuine
  multi-session delegation), which reverse-engineered a 2-surface CLI into **6
  dependency-sequenced stories** (`cli-1…cli-4` foundations first, then
  `greet-1`, `farewell-1`), acceptance criteria pinning exact strings, trailing
  newlines, and exit codes.
- **Migration** — session `98f52fae…` took the **earliest** story (`cli-1`),
  scaffolded CI from scratch in the empty `new:python` target (gate == CI from
  story #1), turned every Given/When/Then into a test, passed both gates, pushed
  `gm/cli-1`, `main` stayed pristine — and the bundle's own eval scored the run
  **CLIMBING ✓** (0/6 → 1/6, lookahead = 0: perfectly in sequence).

Sessions are durable (root + child each persisted `events.jsonl` +
`metadata.json` + `transcript.jsonl`, resumable). That property is load-bearing —
the reality check is what exposed the v0.1.1 `hooks-logging` fix (see
`docs/DESIGN_DECISIONS.md` §10).

## Diagrams

- **Phase 1 flow** (inventory): [`docs/diagrams/inventory.png`](https://github.com/michaeljabbour/amplifier-bundle-genemigration/blob/a20f50716d4bd07053a04b84fe5c50d6eee547ef/docs/diagrams/inventory.png) · **Phase 2 flow** (migration loop): [`docs/diagrams/migrate.png`](https://github.com/michaeljabbour/amplifier-bundle-genemigration/blob/a20f50716d4bd07053a04b84fe5c50d6eee547ef/docs/diagrams/migrate.png) — edge labels = routing; derived from the executable graphs by `python3 docs/diagrams/generate.py`.
- **Bundle structure** (composition + token costs): [`bundle.png`](https://github.com/michaeljabbour/amplifier-bundle-genemigration/blob/a20f50716d4bd07053a04b84fe5c50d6eee547ef/bundle.png) / [`bundle.dot`](https://github.com/michaeljabbour/amplifier-bundle-genemigration/blob/a20f50716d4bd07053a04b84fe5c50d6eee547ef/bundle.dot) (bundle-to-dot v3).

## Layout

| Path | What |
|---|---|
| `bundle.md` · `behaviors/gm-core.yaml` | Root bundle + composable capability set |
| `bundles/` | `gm-pipeline` (headless) · `gm-interactive` (run_pipeline) launchers |
| `agents/` | `gm-inventory` · `gm-orchestrator` · `gm-verifier` (Loop 1) · `gm-expert` |
| `modes/gm.md` | `/gm` migration posture |
| `context/` | `gm-awareness.md` (thin) · `gm-runbook.md` (method) · `story-template.md` |
| `pipelines/` | `inventory.dot` · `migrate.dot` · `verify.dot` (Loop 1) · `ledger.py` |
| `examples/newtui-to-rust/` | Worked instance (Python/Textual → Rust/ratatui) |
| `PRINCIPLES.md` · `docs/DESIGN_DECISIONS.md` | Non-negotiables · why it's shaped this way |

## Principles (full list in `PRINCIPLES.md`)

Behavior is the truth, the inventory is the spec · study deeply, rebuild idiomatically,
never transliterate · sequence is the plan · acceptance criteria are the oracle (and
alive) · the terminal proves parity · gate == CI · never a protected branch · bounded
& never stalled · the source is read-only.
