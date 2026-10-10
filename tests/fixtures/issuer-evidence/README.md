# Issuer evidence source fixtures

`manifest.json` identifies five unmodified public SEC responses captured on
10 October 2026 during the ZIM source review. Each source file retains the exact
response bytes, fetch timestamp, URL, byte count and SHA-256. No fresh network
request is needed to run the tests. The issuer's February announcement and its
later September and October updates describe one unresolved agreement;
stopping an approval application's handling does not establish termination of
that agreement.

ZIM's captured submissions contain 33 current reports in the trailing 365 days.
The February merger report is the seventeenth newest. A latest-three document
capture therefore cannot establish that earlier agreements were reviewed.

`excerpts/` contains explicitly reduced, verbatim passages from the NVDA SEC
responses observed during the same bounded discovery. Its manifest distinguishes
the full response's observed SHA-256 from each stored excerpt's SHA-256. The full
NVDA HTTP bodies were not saved, so these excerpts cannot reproduce those full
body digests. They demonstrate why an acquirer's agreement and a credit-support
agreement must not be treated as evidence that the issuer is a cash-buyout
target. They do not establish that NVDA has no other material events.

Fault cases built in the tests are synthetic parser or transport inputs. They
must not be presented as captured SEC responses or production publications.
Browser receipts, when present, are generated through the production collector
from verified fixture publications; they are not hand-authored publication
records. Fetch success does not mean issuer news or earnings are cleared.

Run `python tests/fixtures/issuer-evidence/generate.py --check` to verify the twelve
producer outputs, or omit `--check` to regenerate them. The generator changes a
synthetic provider's COIL symbol to ZIM before the real evening pipeline runs.
That produces an AAPL ticket and a reviewed ZIM exclusion. Following the
cash-preview fixture convention, the generator keeps the returned deterministic
telemetry, omits the practice-page marker, and verifies production provenance.
The run ID explicitly names this synthetic issuer-evidence control. Its reader
projection comes from those exact canonical bytes. These are production-shaped
offline test records, not actual provider observations or real production runs.

The `collected`, `metadata-only`, `identity-unverified`, `outage` and
`inapplicable` receipt and bundle pairs use a pinned 10 October collection time.
The inapplicable variant uses the real session gate without a fixture override;
it makes no source requests for this older publication and keeps its reviewed
anchors. Browser receipts exercise
the normal `dry_run: false` path with injected offline transports; the browser's
actual publication-hash verification remains active. AAPL's SEC-shaped inputs
are synthetic and labelled in their text. ZIM's supplied responses are the
captured files above. Its uncaptured August document returns an explicit
retrieval failure, so the `collected` variant honestly remains partial. No
fixture generation makes a live provider request or changes trade authority.
