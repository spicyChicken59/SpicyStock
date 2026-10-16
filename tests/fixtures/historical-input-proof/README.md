# Frozen inputs for the historical input proof's offline boundary

`data-symbols-61fa0d91.txt` is `data/symbols.txt` as the original 24 and
25 September 2026 historical runs read it: Git blob
`61fa0d913d509fa3c00d383490028af3cab640f8` at execution revisions
`470c358c06bc9c997184d829c63845c4db0dc4f5` and
`e1359495ad267365dae9b6d03712fe7f17dc70cb` (the same bytes at both), SHA-256
`ff905018446fe42b0167c8d728e70bcdc803e1fbb5511a45ee71adfb0ec19971`, the
`price_exempt_source_sha256` the frozen acquisition manifest records for each
day. `tests/test_historical_input_proof.py` serves it in place of the Git blob
on a shallow checkout and holds it to that digest. It is never the checkout's
own `data/symbols.txt`, which moves whenever a name is retired from the seed;
the production tool reads the blob from Git at the execution revision.
