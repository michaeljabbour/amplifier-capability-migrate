# Migrate

Change the language. Preserve the experience.

Watch the [72-second film](https://michaeljabbour.github.io/amplifier-skill-migrate/#film): an app copied line by line that loses a page of edits, and how the skill moves the behavior instead. The example in it is fictional.

A whole-application migration skill. Observe how the source behaves, turn it into sequenced stories, and rebuild one complete slice at a time with data, failure and recovery checks.

[Explore the site](https://michaeljabbour.github.io/amplifier-skill-migrate/) · [Read the method](skills/migrate/SKILL.md) · [Install guide](docs/INSTALL.md)

## What you get

- **Capture the app people use.** Inventory commands, screens, hidden state, errors and persistence instead of translating files line by line.
- **Rebuild in the target’s idioms.** Use source-derived acceptance criteria while respecting the target language and host architecture.
- **See what is actually complete.** Keep implemented, independently verified, blocked and cut over as separate states.

## Install and try it

Requires Git and Python 3.11+. Run these commands from a terminal:

```sh
git clone https://github.com/michaeljabbour/amplifier-skill-migrate.git
cd amplifier-skill-migrate
python3 scripts/capability.py doctor
python3 scripts/capability.py install --dest ~/.agents/skills
```

The installer copies `skills/migrate` as a complete folder into your chosen skills parent. Use the discovery path supported by your agent. It starts no service and configures no provider. Restart or refresh skill discovery in your host, then ask:

```text
Use Migrate to inventory this fictional terminal editor for a Rust rebuild. Keep the Python source read-only. Start with open, edit, save and failed-save recovery; write dependency-ordered story cards and acceptance probes before implementation.
```

If your agent does not discover installed skills, point it directly at the complete folder and ask it to read `SKILL.md`. Reading the method needs no Python runtime. [Installation details](docs/INSTALL.md) cover conflict handling and optional native execution.

## How the work proceeds

1. **Inventory the source.** Keep it read-only and describe observed capabilities as dependency-ordered stories with testable criteria.
2. **Rebuild a vertical slice.** Write target checks and a real-surface probe first; include data handling and recovery.
3. **Verify and plan cutover.** Challenge behavior against the source, preserve failures and record migration and rollback status.

## Example output

Fictional worked example. It illustrates the intended output; it is not a measured result or a real customer story.

```text
Fictional story: recover from failed save
Given: edited buffer and unwritable destination
When: save fails
Then: buffer remains; reason is visible; retry is possible
Depends on: editor state and file boundary
Evidence: source observation + target terminal probe
State: inventoried; target implementation pending
```

## What is checked

Retained graph syntax, ledger ratchet and sequence fixtures pass, and the portable install is checked. They validate orchestration mechanics; this release does not claim a newly completed app migration or production cutover. See [validation](docs/VALIDATION.md) for the exact checks and limits.

## Retained implementation and references

[Migration map](docs/MIGRATION.md) records the original source paths and current roles. Primary Git history, native engines, tests, examples, and evaluation assets remain in this checkout. [Native guide](docs/NATIVE-README.md) preserves the original project documentation; old install URLs and runtime claims there are historical and need current verification. [Validation](docs/VALIDATION.md) records actual checks and limits.

## Build the site

```sh
python3 scripts/capability.py build
python3 scripts/capability.py check
```

The static site includes a ZIP built from the canonical method, references and license. Runtime and provider setup remain separate from installing the portable method.

## Repository migration

This repository was renamed from `amplifier-skill-migrate` to `amplifier-capability-migrate`. Existing installed method names, bundle aliases and native interfaces stay the same. See the [migration guide](https://michaeljabbour.github.io/migration/) and [repository map](https://michaeljabbour.github.io/migration/mapping.json) for source URL updates.
