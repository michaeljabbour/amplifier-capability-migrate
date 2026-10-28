# Gene-Migration Principles

The non-negotiables. If a run violates one of these, stop it.

1. **Behavior is the truth; the inventory is the spec.** Stories capture what the
   app DOES (user-observable), derived from code AND live observation. The migration
   answers to the acceptance criteria — never to "what the source's language
   happened to do."

2. **Study deeply, re-implement idiomatically, never transliterate.** A migration
   reads the source without apology — fidelity demands it — but the target is
   written in the target language's own idioms. Line-by-line translation is a defect.

3. **Sequence is the plan.** Foundational stories (data model, core loop,
   primitives, protocol) migrate before the features that consume them. The
   backlog's file order IS the dependency order; the loop takes earliest-first.

4. **Acceptance criteria are the oracle — and they are alive.** Every Given/When/
   Then becomes a target-language test plus a forge assertion. When a gate failure
   proves a criterion wrong, fix the STORY CARD, not just the code — and never
   force-green.

5. **The terminal proves parity.** A story is done when the migrated app exhibits
   the behavior through a real terminal (forge), not when unit tests pass.

6. **Gate == CI.** The local gate runs exactly what the target's CI runs; a new
   target repo gets its CI scaffolded with story #1.

7. **Never a protected branch.** One PR per story, branch `gm/<story>`, gates green
   before the PR opens.

8. **Bounded, never stalled.** ≤3 attempts per story; then `acknowledged` + a human
   handoff file, and the sequence keeps moving.

9. **The source is read-only.** The migration never edits, patches, or "fixes" the
   source app.
