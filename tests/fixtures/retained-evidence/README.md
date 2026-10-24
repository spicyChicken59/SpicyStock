# Retained evidence objects the tests read

Every object here is a byte-for-byte copy of `docs/evidence/<name>` at commit
`bef7dd67` (24 October 2026), and each is named by its own content digest:
`tests/test_evidence_retention.py` holds every copy to its name, and the reads
go through `provenance._object()`, which refuses a changed byte. They are
exactly the 497 objects the suite and the two fixture generators read from the
live archive that day, found by recording every read under `docs/evidence`
during a full run of `pytest tests/` and of
`tests/fixtures/stop-research/generate.py` and
`tests/fixtures/research-outcomes/generate.py` with `--check`:

- the 487 source frames, reader prompts and chart images of the actual
  October 9 publication (`43dcb8d7`, canonical `f5cbe38e...`), which the
  stop-research and research-outcomes fixtures verify in full;
- the provider placeholders `tests/test_followup.py` reads;
- the two dated frames `tests/test_reader_authority.py` replays from the
  22 September reader-downgrade audit;
- the CRL and IQV source frames of the frozen validation cases, which
  `tests/test_historical_input_proof.py` hands to
  `tools/historical_input_proof.volume_sensitivity()`.

A full run with `docs/evidence` deleted is how the list was proved complete:
the one read the recording had shown and the repointing first missed (the
volume reading's fixed path) failed there and nowhere else.

`docs/evidence` keeps only what a served file names (`provenance.prune_objects()`),
so the October 9 publication's objects leave it once the recovery catalog drops
that night. A test reads these copies, never the rolling archive.
