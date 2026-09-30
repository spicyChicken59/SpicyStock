# Exact public-digest continuation

The four findings retained in the [previous observation](../bounded-correction/final-local-scan-findings.json)
were independently reverified at `65cd32ba0991ecad4bb04d53132d4a44889aca32`.
Two occurrences identify the same official age v1.3.2 executable; the other
two identify the historical committed scanner test/support source bytes.
The retained executable matches its archive member, and the retained archive
matches the committed official-release installer pin. These source digests
describe the historical files, not the later edits to those test files.

Two additional rule-specific AND dispositions cover exactly those pairs:
one executable digest at the two exact supervisor evidence paths, and the two
historical source digests at the exact focused-test receipt path. No file,
directory, detector, commit, or history segment is excluded. Earlier dispositions
and every default detector remain enabled. All previous evidence is unchanged.

[The compact receipt](scanner-controls.json) records the binary provenance,
source identities, commands and results. Before the configuration change, the
actual Gitleaks 8.24.3 harness had three expected acceptance failures containing
the four findings; its other 22 controls passed. After the change, all **25
actual-engine controls passed**, including unrelated values at each permitted
path, correct values elsewhere, values crossed between the two new path groups,
and a separate default detector. Generated canary values and raw finding logs
are not published here.

The normal-collected regressions failed without the change (**5 failed, 37
passed**) and passed after it (**43 passed**, including one existing fixture
control). An initial CLI attempt stopped at a Windows scratch path-length error;
the harness now uses short numbered case directories. The cited before/after
CLI attempts both completed after that correction.

Actual scans of the unchanged PR first-parent range `7c0d35d^..65cd32ba`
reported four findings with the old configuration and zero with the new one.
This local comparison does not claim a final pushed-head hosted scan result,
authorize historical acquisition, or change any capacity finding.
