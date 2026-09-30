# Conversion evidence representation

This record belongs to the existing [execution handoff](../2026-09-29-historical-execution.md).
Authority: [Guidance comment 5903186288](https://github.com/spicyChicken59/SpicyStock/pull/95#issuecomment-5903186288).
The accepted hosted rehearsal and owner-side replay are preserved; neither ran
the new representation. This document grants no execution approval.

The old adapter retained one dictionary for each inexact field, with `symbol`,
`session`, `field`, `decimal` and `float64_hex`. The [untouched-adapter record](untouched-adapter.json)
was produced from the actual unedited main `6284cb9787c11929eaedf1a263cf463ab4ae4928`
using invented decimal inputs. Its normalization source content SHA-256 is
`f1ae88dae57ee114a0a6b55b3f0d382e1f150e21cc4716c76e4392f317d51ef2`.
This is a synthetic reproduction, not an observation about provider data.

## Version 2

`historical-reconciliation-v2` explicitly contains
`historical-float64-projection-v2` entries. The projection stores one
`[selected_row_ordinal, field_mask, float64_hex_values]` record per replayable
selected row, including zero masks. The field order is exactly Open, High, Low,
Close, Volume; bit zero is Open. Binary-hex strings are complete `float.hex()`
values. They are not rounded or shortened.

Ordinals enumerate canonical query symbols and their selected row order. Query
identity, a canonical query hash and a canonical complete-normalization hash
bind the projection to its query, basis, target, securities, normalized decimal
strings, selected raw pointers, discarded duplicate lineage and invalid/missing
states. Identical tickers and dates in different queries cannot share an unbound
projection. A content hash here binds retained context; it does not replace any
required conversion facts or establish provider provenance.

`iter_projection_conversions` verifies the complete compact structure and
context before yielding the first legacy fact. It checks ordinal completeness,
masks, counts and exact binary values against the retained decimal strings,
then iterates without allocating an expanded legacy list. Decimal strings are
returned directly from the normalized row. They do not retain every possible
original JSON spelling: the unchanged raw page remains authoritative.
Selected timestamps must be ordered and unique for each security; selected
source coordinates cannot be reused by that security. Source symbols, page
indices/hashes, non-boolean row indices and the explicit page limit are checked.
The decoder uses a bounded set of source coordinates for one security at a time,
in addition to the retained input and compact records.

Invalid symbols remain excluded from replay. Missing rows, partial pagination,
unknowns, decimal event audits, original-population limitations and reader
uncertainty retain their original meanings. Empty conversion evidence is an
explicit validated state; missing evidence is not treated as empty.

`frames_for_replay` retains its explicit `historical-float64-projection-v1`
contract for legacy fixtures. The new reconciliation path selects version 2
directly, without first building the redundant per-field dictionaries. No
accepted output or hash is rewritten. Output-byte reproducibility still requires
identical source bytes and dependency behavior; schema versioning does not hide
the earlier CRLF provenance failure.
`reconcile(..., projection_contract=LEGACY_PROJECTION)` explicitly reproduces
the v1 output for fresh offline fixtures. This is not a workflow-dispatch input
or permission to replay the owner's accepted private package in this task.

## Execution boundary

The current workflow, policy, guard, acquisition wrapper, package/recovery code
and original recovery contract remain unchanged. They intentionally refuse to
approve the changed tools using PR #95's checkout or its accepted recovery.
The [binding controls](binding-controls.json) demonstrate that removing each
reviewed-head, source-tree or recovery check makes its intended test fail while
the other controls pass. No live runtime identity or readiness was fabricated.

The read-only implementation-side [review](independent-review.json) supplements
the tests; it is not Guidance acceptance. Guidance review is NOT RUN for
this new implementation.

The separate prospective compatibility proposal is a review decision, not an
operative gate. Real execution remains BLOCKED for technical release review.
[The later owner direction](https://github.com/spicyChicken59/SpicyStock/pull/95#issuecomment-5903266884)
records personal use and ends licensing/outreach work; it does not establish
provider consent or change the guard. Obsolete project attestations need an
explicit reviewed adjustment. Neither a compaction merge nor a synthetic capacity
result releases provider access.
