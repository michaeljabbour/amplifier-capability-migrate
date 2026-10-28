# User-story + acceptance-criteria template (inventory output)

The `gm-inventory` agent writes one file per surface at
`inventory/stories/<surface>.md`, containing one or more stories in THIS shape.
Robustness = behavior captured precisely enough that a migrator who never saw the
source could rebuild it and a test could prove it.

```
## <story-id>  —  <short title>

**Story.** As a <role>, I want <capability>, so that <benefit>.

**Acceptance criteria.**
- GIVEN <precondition/state> WHEN <user action> THEN <observable result>.
- GIVEN … WHEN … THEN …            (cover the happy path AND the edges/errors)

**Observable contract.** Exact user-visible strings, layout, keybindings, states,
and error messages the migration must preserve (only where acceptance depends on
them — not incidental styling).

**Source pointers.** <file:symbol> in the source app that implements this (reference
for the migrator; never to be copied — the target is idiomatic).

**Depends-on.** <story-ids or surfaces> this builds on (drives sequencing:
foundational stories — data model, core loop, primitives, protocol — come first).

**Notes.** Anything language-idiom-specific in the source that should be DISCARDED
(not carried into the target).
```

Rules:
- Stories describe **user-observable behavior**, never implementation. "How the
  source's language happens to do it" is noise; capture what the user experiences.
- Every acceptance criterion must be **concrete and testable in the target
  language** — if you can't imagine the test, the criterion is too vague.
- Prefer several small, independently-verifiable stories over one giant story.
