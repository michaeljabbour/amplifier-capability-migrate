---
name: migrate
description: Use when behavior, data, interfaces, and deployment must survive a whole-app migration.
license: MIT
---

# Migrate

Change the language without losing the application.

## Two phases, one behavioral contract

Migrate the whole application's behavior, not its syntax. The original [principles](references/PRINCIPLES.md), [story format](references/story-template.md), and [runbook](references/gm-runbook.md) preserve the distinct two-phase method and optional native graph interface. Historical model names and “proven” statements are context for that engine, not current requirements or comparative results.

## Inventory the source

1. Declare read-only source, target language/runtime, included surfaces, excluded work, data stores, protocols, deployment targets, and rollback needs. Preserve original data and capture a recoverable snapshot before any authorized migration of it.
2. Inspect source code and operate the real app where available. Inventory screens/commands/flows, hidden state, edge cases, errors, persistence, and recovery. Label inferred behavior that could not be observed.
3. Write one story per observable capability with source evidence, Given/When/Then criteria, data/interface compatibility, and concrete checks. A builder who never saw the source should be able to implement from the card.
4. Order stories by real dependencies: storage/model/protocol primitives before their consumers. Record depends-on explicitly. File order is the default sequence, not proof that arbitrary stories can run in parallel.

## Rebuild one vertical slice

Observe the selected source behavior; distinguish what to preserve from source-language idioms to discard. Write the target acceptance test and real-surface probe before implementation. Rebuild idiomatically, using existing target seams. Deliver feature, tests, normal CI gate, state/data handling, and recovery together. Terminal apps need a real-terminal check; GUI, API, or service surfaces need their corresponding real observable checks. Unit tests alone do not prove parity.

Use an isolated branch; keep protected branches and publication outside the loop until authorized. Bound attempts (the retained engine uses at most three), then record acknowledged blocker with a reproducible case and smallest handoff. Acknowledged is not implemented or verified.

## Independently verify

After the builder's checks, derive verification from the source behavior with only the story identity and intended scope—not builder claims, implementation, or builder-authored expected answers. Record the independence actually achieved. A second role using the same model is not independent human evidence. Failed verification reopens the story within a declared bound; preserve findings. If the criterion was wrong, propose and adjudicate a story amendment with evidence; never silently weaken it to pass.

## Finish with evidence

Return inventory coverage, story states, exact unit/real-surface commands and results, data/rollback status, independent findings, blocked stories, and known behavior differences. “Implemented,” “verified,” “acknowledged,” “cut over,” and “accepted by users” are separate states. The repository's ledger/eval self-tests validate mechanics, not a completed migration.
