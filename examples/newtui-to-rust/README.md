> Local paths in this document are illustrative placeholders. Replace each with the appropriate absolute path on your machine before following an example.

# Example instance — newtui (Python) → newtui-rust (Rust)

The migration you are probably already doing by hand. GM formalizes it: reverse-
engineer the Python/Textual app into a sequenced story inventory, then rebuild it in
Rust/ratatui story-by-story, each story proven by its acceptance criteria + a forge
boot of the Rust binary. This supersedes maintaining PARITY.md/MIGRATION.md manually
— the inventory IS that plan, generated and kept live by the loop.

## Knobs

- **source:** `/absolute/path/to/source-python-repository` · `SOURCE_KIND=python`
  (read + observe only).
- **target:** `/absolute/path/to/target-rust-repository` · `TARGET_KIND=rust`.
  Its existing PARITY.md/MIGRATION.md are the seed the inventory reconciles with.
- **inventory home:** `<target>/inventory/` (surfaces.tsv, stories/, backlog.tsv).

## Env for a run

```sh
export SOURCE_PATH=/absolute/path/to/source-python-repository   SOURCE_KIND=python
export TARGET_PATH=/absolute/path/to/target-rust-repository TARGET_KIND=rust
export FORGE_TOOL=/absolute/path/to/forge-tool
export LEDGER_TOOL=/absolute/path/to/ledger-tool
export SURFACES=$TARGET_PATH/inventory/surfaces.tsv
export BACKLOG=$TARGET_PATH/inventory/backlog.tsv
```

## Sequence sketch (what SequenceBacklog should produce)

Foundational first — the codex-core/codex-tui split, the `serve` stdio protocol
client, session model, event loop — THEN the interactive surfaces (composer, footer,
mode switch, approvals/needs-you, plan drilldown), THEN feature surfaces (fork,
resume, providers, routing, notifications). A story migrates only after its
depends-on stories are `implemented`; independent surfaces parallelize.

## Run

1. **Phase 1 (inventory):** `/gm` then delegate to `gm-inventory` (or run
   `pipelines/inventory.dot`) — enumerates surfaces, derives stories + acceptance by
   observing the real Python TUI via forge, writes the sequenced backlog into the
   Rust repo's `inventory/`.
2. **Review** the backlog + a sample of story cards. Fix any vague acceptance.
3. **Phase 2 (migrate):** delegate to `gm-orchestrator` (or run
   `pipelines/migrate.dot`) — rebuilds each story in Rust, gated by `cargo test` +
   `clippy` + a forge boot of `amplifier-newtui-rs` asserting the acceptance, one PR
   per story on `gm/<story>`.

> The Rust client is a protocol client of the Python `serve` backend, so many stories
> are "render protocol state X" — their acceptance is about the Rust UI's observable
> behavior, with the Python backend as the source of truth.
