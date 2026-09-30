# Bounded scanner correction

This implementation-side check addresses exactly two public GitHub API-response
digests in the existing [CI observation](../candidate-final-ci/secret_scan-api.json).
The rule-specific disposition requires both that exact repository-relative path
and either exact digest. Default detectors and the earlier fixture exceptions
remain enabled. It does not exclude a directory, a file generally, or a detector.

[The compact receipt](scanner-controls.json) records the official Gitleaks 8.24.3
Windows release URLs, the archive checksum verified against the published release
checksums, the executable digest, commands, source identities and actual results.
The offline harness takes an explicitly supplied binary and uses fresh scratch
outside Git. It neither installs tools nor reads live credentials. The public
receipt includes no generated canary values or raw detection logs.

Seven actual-engine controls passed:

| Input | Actual scanner result |
| --- | --- |
| Original observation with defaults only | Exit 2; two generic-key findings |
| Original observation with the narrow disposition | Exit 0; no findings |
| Unrelated invented generic key at the exact path | Exit 2; one generic-key finding |
| Same two public values in a sibling file | Exit 2; two findings |
| Same values at a path with an added suffix | Exit 2; two findings |
| Same values under an added directory prefix | Exit 2; two findings |
| Invented value matching another default detector at the exact path | Exit 2; one `github-pat` finding |

The actual existing PR first-parent range from `7c0d35d^` through `bd779c2` was
also scanned twice, using its unchanged ignore file. The committed old
configuration produced the two reported findings; the corrected configuration
produced zero. History was not rewritten. A separate actual-engine directory
scan of the correction files and public evidence also produced zero findings.

The normal-collected configuration regressions contribute ten cases. Those and
two existing fixture controls passed together: **12 passed** with the established
UTF-8 Windows test environment. The receipt preserves an earlier wider local
attempt's **32 passed, 1 failed** result when that environment variable was
omitted; its one failing existing case passed when the environment was restored,
without a grader or fixture change.

These observations establish the local disposition boundaries. The final pushed
head still requires its own hosted scan result; these controls do not assert
that future result or change the historical-data release status.
