# Migrate

Change the language without losing the application.

Developers rebuilding a whole application in another language or runtime. Use when behavior, data, interfaces, and deployment must survive a whole-app migration.

## Install the portable method

```sh
python3 scripts/capability.py doctor
python3 scripts/capability.py install --dest ~/.agents/skills
```

Keep the complete `skills/migrate` folder together. Installation copies only that method, references, and license; it starts no service and installs no runtime. Use a different skills-parent path for your host.

## Choose the mode

- **Inventory** — The source app must become a rebuildable specification. Observed surfaces, sequenced story cards, data/interface contracts, and acceptance criteria.
- **Rebuild** — A story’s prerequisites and acceptance are known. An idiomatic vertical slice with unit and real-surface evidence.
- **Verify** — Builder-created checks need an independent challenge. Source-derived parity findings, bounded reopen decisions, and retained unresolved cases.

## What was consolidated

[Migration map](docs/MIGRATION.md) records the original source paths and current roles. Primary Git history, native engines, tests, examples, and evaluation assets remain in this checkout. [Native guide](docs/NATIVE-README.md) preserves the original project documentation; old install URLs and runtime claims there are historical and need current verification. [Validation](docs/VALIDATION.md) records actual checks and limits.

## Build the local site

```sh
python3 scripts/capability.py build
python3 scripts/capability.py check
```

Open `_site/index.html` or serve `_site` with a local static server. The downloadable ZIP is built from canonical method bytes. The fictional before/after example illustrates intended judgment; it is not a measured improvement. Nothing has been published or renamed remotely.
