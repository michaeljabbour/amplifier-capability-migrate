# GM Runbook — how to drive a Gene-Migration run

You are the **orchestrator/engine** for a whole-app language migration. Two phases,
in order. The graphs (`gm:pipelines/inventory.dot`, `gm:pipelines/migrate.dot`) are
the executable spec; the proven default is orchestrator-as-engine (you drive the
loop with self-delegated workers). Both graphs also run under `run_pipeline`.

## The knobs

| Knob | Meaning |
|---|---|
| **source** | The app being migrated: `SOURCE_PATH` + `SOURCE_KIND` (language A). Read + observe only — never edited. |
| **target** | The migration home: `TARGET_PATH` + `TARGET_KIND` (language B). May be a **new/empty repo** — story #1 scaffolds `./ci/gate.sh` + the CI workflow. |
| **inventory** | Where the reverse-engineered plan lives: `$TARGET_PATH/inventory/` (surfaces.tsv, stories/, backlog.tsv). Committed to the target repo — it IS the living migration plan. |

Also: `FORGE_TOOL` (forge.py abs path) · `LEDGER_TOOL` (this bundle's
`pipelines/ledger.py` abs path — decoupled from either repo) · `SURFACES` /
`BACKLOG` (abs paths to the two TSVs).

## Phase 1 — INVENTORY (reverse requirements engineering)

Goal: turn the source app into **robust user stories + testable acceptance
criteria, dependency-sequenced**. Follow `gm:context/story-template.md` exactly.

1. **Enumerate surfaces** — study the source top-level AND boot it via forge to see
   its real user-facing surfaces (screens, commands, flows). Seed `surfaces.tsv`.
2. **Per surface** (parallelizable, one worker per surface): study the code AND
   drive the surface in forge; write `inventory/stories/<surface>.md` — stories
   (As a/I want/so that), Given/When/Then acceptance covering happy path AND edges,
   observable contract, source pointers, depends-on.
3. **Sequence** — one global pass orders ALL stories by dependency (data model,
   core loop, primitives, protocol FIRST; features that consume them after) and
   writes `backlog.tsv` in that order. **File order = migration order** (the ledger's
   `earliest` returns the next story). Vague acceptance gets fixed here, not later.

Quality bar: a migrator who never saw the source could rebuild each story from its
card, and a test could prove it. Behavior, never implementation.

## Phase 2 — MIGRATION (the attractor loop)

Iterate `backlog.tsv` earliest-first (= dependency order). Per story:
1. **StudySource** — read the source implementation deeply (this is a migration:
   fidelity is the goal) and observe it live via forge; record what to PRESERVE
   (behavior, states, exact strings where acceptance depends on them) and what to
   DISCARD (source-language idioms).
2. **PlanPort** — design the **idiomatic** target implementation reusing earlier
   migrated stories; turn EVERY acceptance criterion into a concrete target test;
   author the forge probe FIRST (the probe is the spec).
3. **Implement the vertical slice** — target code + acceptance tests + forge probe
   + CI parity in one pass. Gate == CI. Never transliterate.
4. **Unit gate** (target kind) → **forge gate** (boot the migrated app; assert the
   acceptance criteria) → **PR** (branch `gm/<story>`, label `gene-migration`) →
   mark `implemented`.
5. Bounded ≤3 attempts → `acknowledged` + `.ai/gm_blocked/<story>.md`, move on.
   If a failure reveals the acceptance criteria were wrong, FIX THE STORY CARD —
   the inventory is a living artifact.

**Parallelism:** the sequence is a dependency ORDER, not a serialization — stories
whose depends-on are already `implemented` may run in parallel lanes (git worktrees,
one worker each, ~4–6 max; forge probes flake under heavier load — re-run an
isolated forge failure before burning a retry). `claude-opus-4-8` workers only.

## run_pipeline launch (alternative engine)

```python
from amplifier_module_pipeline_runner.runner import run_pipeline
await run_pipeline(open("pipelines/migrate.dot").read(),
    params={"SOURCE_PATH": "...", "TARGET_PATH": "...", "TARGET_KIND": "rust",
            "FORGE_TOOL": ".../forge.py", "LEDGER_TOOL": ".../pipelines/ledger.py",
            "BACKLOG": ".../inventory/backlog.tsv"},
    cwd="<TARGET_PATH>", logs_root="./runs")
```
Or export the same names as env vars before `amplifier run` — `${VAR:?}` guards
fail loud. (A mounted orchestrator's `config.params` does NOT reach `tool_command`.)

## Loop 1 — blind verification (after rows land)

Rows landed by the build loop are `implemented` — gated, but by gates the flow
itself authored. Loop 1 (`gm:pipelines/verify.dot` · the `gm-verifier` agent)
independently drives them to the terminal state **`verified`**: a verifier BLIND to
every builder artifact derives its own checks from the ground truth (the SOURCE app, knowing only the story id + title)
and validates through a real terminal. Fail ⇒ findings in `.ai/verify_findings/`,
row reopens ONCE (`implemented → new` — the build loop rebuilds with findings
readable), then `acknowledged`. Verifier → builder info flow is allowed; builder →
verifier is forbidden. Story-card amendment proposals (.ai/gm_amendment_proposals/) are accepted or rejected ONLY here or by a human.
Run order: build loop to quiescence → verify loop to quiescence → done when every
row is `verified` or `acknowledged`. Monitor with `evals/hillclimb.py --verifier`.
