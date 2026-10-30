# AGENTS.md — amplifier-bundle-genemigration

**What this repo is:** a self-contained Amplifier bundle packaging **GM (Gene
Migration)** — a two-phase attractor that migrates a whole app from one language to
another: Phase 1 reverse-engineers the source into dependency-sequenced user stories
+ testable acceptance criteria (the inventory); Phase 2 rebuilds it story-by-story in
the target language, gated by those criteria + a real-terminal forge check.

**Read `PRINCIPLES.md` before changing behavior** — behavior-is-truth, idiomatic-
never-transliterated, sequence-is-the-plan, living acceptance criteria, gate == CI.

## Key directories
| Path | What |
|---|---|
| `bundle.md` | Root bundle (thin; includes `gm:behaviors/gm-core`) |
| `behaviors/gm-core.yaml` | Composable capability set (tools, mode system, agents, awareness) |
| `bundles/` | Launchers: `gm-pipeline` (headless), `gm-interactive` (run_pipeline) |
| `agents/` | `gm-inventory` (reverse-engineers the spec) · `gm-orchestrator` (migrates) · `gm-expert` (plans) |
| `modes/gm.md` | The `/gm` migration posture (auto-discovered) |
| `context/` | `gm-awareness.md` (thin) · `gm-runbook.md` (method) · `story-template.md` (the story format) |
| `pipelines/` | `inventory.dot` (Phase 1) · `migrate.dot` (Phase 2) · `ledger.py` (stdlib, `LEDGER_FILE`-aware) |
| `examples/newtui-to-rust/` | Worked instance: Python/Textual app → Rust/ratatui |
| `docs/DESIGN_DECISIONS.md` | Why it's shaped this way (incl. GM-vs-HGT and param decisions) |

## Verification gradient (before a PR)
- **Structural:** graphviz parses BOTH dots; `python3 pipelines/ledger.py stats` runs.
- **Eval:** `python3 evals/hillclimb.py --self-test && python3 evals/hillclimb.py --fixture` (the hill-climbing eval and its regression + sequence detectors pass).
- **Conformance:** `/audit-bundle` + `validate-bundle-repo`.
- **Live run** (required when touching graphs/orchestration): inventory a small
  scratch app, then migrate one story green end-to-end.
- Regenerate `bundle.dot`/`bundle.png` (bundle-to-dot) before the PR.
- Regenerate the pipeline doc diagrams after any graph change: `python3 docs/diagrams/generate.py` (derived views; never edits the executable graphs).

## Pitfalls
- NEVER remove `hooks-logging` from the behavior: it is what makes sessions durable (creates the session dir + events.jsonl). Without it `amplifier run` finishes but persists nothing and errors `Session '<id>' not found` at finalize — found via DTU reality check.
- Params reach `tool_command` only via env vars / run_pipeline — never a mounted
  orchestrator's `config.params` (see DESIGN_DECISIONS.md §4).
- Never remove `... && printf pass || printf fail` from a gate node (stale
  last_line misroutes on non-zero exit).
- `inventory/` artifacts belong to the INSTANCE (the target repo), not this bundle.
- Agents declare inline non-pipeline orchestrators — keep them (recursion guard).

## Market research upkeep

Local-only market research lives in `.research/market/` (gitignored; never commit it).

At session start, check `.research/market/last_updated`:
- If the file is missing, seed it from this repository's README and capability source/provenance links, using cited primary sources and local retrieval dates.
- If it is older than 30 days, or before any positioning, launch or naming work, refresh it with cited primary sources (URL + retrieved date).
- Keep it local. Never commit it and never copy private research into public docs.
- Log every change in `.research/market/CHANGELOG.md`.

## Capability identity

Public capability identity: `amplifier-capability-migrate`. Preserve the existing portable method folder, native interfaces and legacy installation routes across the approved repository rename.
