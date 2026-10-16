"""Refresh branch-based Pages after a bot commit and verify what readers get.

GitHub documents that GITHUB_TOKEN pushes do not trigger Pages builds. The
publication workflow requests one explicitly, then checks every public file
against the committed checkout: the HTML, the records app.js fetches (the two
the run writes and the two historical findings files the Record view reads),
each script and stylesheet the page loads, and the vendored design system it
is drawn on. The list is read off ``docs/index.html`` (``public_files``) so it
cannot fall behind the page; the fetched records are named in ``RECORD_FILES``
because the page does not link them. No market-data, scoring or delivery credentials are used, and
no scan artifacts are read.
"""
from __future__ import annotations

import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

# The workflow runs this file directly with a standard-library-only Python.
# Resolve the sibling source package from this checkout, never the caller's cwd.
SOURCE_ROOT = Path(__file__).resolve().parent.parent
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))
from src import reader


# Fixed records that runtime JavaScript fetches without an index.html link:
# canonical and compact publications, picks, and the two historical findings
# files. The currently referenced observation sidecar is validated separately.
# The archived history and
# evidence objects the page also fetches (docs/history, docs/evidence) are not
# listed: each is named by its SHA-256 and the page checks that digest itself
# (publicJSON), so a stale served copy is refused rather than shown. The
# study's frozen case files under docs/historical-validation/ ARE listed
# (``study_case_files``): the study names each one and its digest, the Record
# view reads nothing else for a case, and a missing one is a 404 the page
# cannot repair. Before the findings files were named here, a JSON fetched only
# from app.js was never verified, and the gate printed "Verified" over a served
# site that could have lacked it.
RECORD_FILES = ("data.json", "reader.json", "picks.json", "historical-validation.json", "historical-findings.json")
OPTIONAL_RECORD_FILES = ("morning.json", "research-observations.json", "source-recovery.json")
WAIT_SECONDS = 480


def reader_asset(docs: Path, name: str, maximum: int) -> bytes:
    """Read a bounded regular checkout asset without following any symlink."""
    parts = Path(name).parts
    if not parts or Path(name).is_absolute() or any(part in ('.', '..') for part in parts):
        raise ValueError('invalid reader asset path')
    path = docs
    if path.is_symlink() or not path.is_dir():
        raise ValueError('reader docs root must be a directory')
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('reader asset cannot follow a symlink')
    if not path.is_file():
        raise ValueError('reader asset must be a regular file')
    with path.open('rb') as handle:
        raw = handle.read(maximum + 1)
    if not raw or len(raw) > maximum:
        raise ValueError('reader asset bytes exceed bound')
    return raw


def reader_files(root: Path) -> tuple[str, ...]:
    """Verify the exact source, projection and fixed-grammar sidecar first."""
    docs = root / 'docs'
    try:
        canonical_raw = reader_asset(docs, 'data.json', reader.MAX_PUBLICATION_BYTES)
        reader_raw = reader_asset(docs, reader.READER_FILE, reader.MAX_READER_BYTES)
        ref = reader.parse_reader(reader_raw)['retained_observations']
        # parse_reader permits only reader-observations/<lowercase SHA>.json.
        observations_raw = reader_asset(docs, ref['path'], ref['bytes'])
        reader.validate_bundle(canonical_raw, reader_raw, observations_raw)
    except (OSError, ValueError, TypeError, KeyError):
        raise RuntimeError('Reader companions do not match the committed canonical publication.') from None
    return (ref['path'],)


def issuer_files(root: Path) -> tuple[str, ...]:
    """Check an optional dated receipt and its own immutable companion.

    An evening publication naturally supersedes yesterday's issuer binding.
    Validate self-integrity here; the browser separately refuses stale binding.
    That normal state must not block publication of the new evening record.
    """
    docs = root / 'docs'
    path = docs / 'issuer-evidence.json'
    if not path.exists() and not path.is_symlink():
        return ()
    from src.issuer_evidence import parse_receipt, validate_bundle
    try:
        receipt_raw = reader_asset(docs, 'issuer-evidence.json', 64 * 1024)
        receipt = parse_receipt(receipt_raw)
        ref = receipt['bundle']
        bundle_raw = reader_asset(docs, ref['path'], ref['bytes'])
        validate_bundle(receipt_raw, bundle_raw)
    except (OSError, ValueError, TypeError, KeyError):
        raise RuntimeError('Issuer evidence companion does not match its committed receipt.') from None
    return ('issuer-evidence.json', ref['path'])


def stop_research_files(root: Path) -> tuple[str, ...]:
    """Verify an optional research receipt and only its referenced cohort.

    Older valid receipts may remain after an optional derivation refusal;
    their source binding is checked by the browser before display. The
    append-only cohort index and unreferenced cohorts are not browser assets.
    """
    docs = root / 'docs'
    path = docs / 'stop-research.json'
    if not path.exists() and not path.is_symlink():
        return ()
    from src.stop_research import MAX_RECEIPT_BYTES, parse_receipt, validate_bundle
    try:
        receipt_raw = reader_asset(docs, 'stop-research.json', MAX_RECEIPT_BYTES)
        receipt = parse_receipt(receipt_raw)
        ref = receipt['bundle']
        bundle_raw = reader_asset(docs, ref['path'], ref['bytes'])
        validate_bundle(receipt_raw, bundle_raw)
    except (OSError, ValueError, TypeError, KeyError):
        raise RuntimeError('Stop research companion does not match its committed receipt.') from None
    return ('stop-research.json', ref['path'])


def research_outcomes_files(root: Path) -> tuple[str, ...]:
    """Verify the optional current journal receipt and its immutable snapshot.

    Older valid bindings remain deployable after an optional writer refusal;
    the browser separately refuses their attachment to a different record.
    The append-only index and other snapshots are not implicit browser reads.
    """
    docs = root / 'docs'
    path = docs / 'research-outcomes.json'
    if not path.exists() and not path.is_symlink():
        return ()
    from src.research_outcomes import MAX_RECEIPT_BYTES, parse_receipt, validate_bundle
    try:
        receipt_raw = reader_asset(docs, 'research-outcomes.json', MAX_RECEIPT_BYTES)
        receipt = parse_receipt(receipt_raw)
        ref = receipt['bundle']
        bundle_raw = reader_asset(docs, ref['path'], ref['bytes'])
        validate_bundle(receipt_raw, bundle_raw)
    except (OSError, ValueError, TypeError, KeyError):
        raise RuntimeError('Research outcomes companion does not match its committed receipt.') from None
    return ('research-outcomes.json', ref['path'])


STUDY_FILE = "historical-validation.json"
STUDY_CASE_DIR = "historical-validation"
MAX_STUDY_BYTES = 1024 * 1024


def study_case_files(root: Path) -> tuple[str, ...]:
    """The validation study's frozen case files, each held to the digest the
    study recorded for it.

    The Record view inspects a case from docs/historical-validation/<record>/,
    byte copies tools/freeze_validation_cases.py made of the archive originals,
    because docs/history keeps a 21-day window that drops the 24 September
    record with the 16 October publication. A study without cases -- no ``cases`` field, an
    empty list or null, as the synthetic roots the tests build -- names no
    files. A case file the study names that is missing, unreadable or not the
    study's bytes is a 404 or a refused integrity check for every reader, so it
    is named here and raises rather than being skipped."""
    docs = root / 'docs'
    from tools.freeze_validation_cases import FreezeError, case_files
    try:
        study = json.loads(reader_asset(docs, STUDY_FILE, MAX_STUDY_BYTES))
    except (OSError, ValueError):
        raise RuntimeError('The validation study file is missing or unreadable.') from None
    if not isinstance(study, dict) or not study.get('cases'):
        return ()
    try:
        files = case_files(study)
    except FreezeError as exc:
        raise RuntimeError(f'The validation study names a case the publication cannot serve: {exc}') from None
    names = []
    for rel, meta in sorted(files.items()):
        name = f'{STUDY_CASE_DIR}/{rel}'
        try:
            raw = reader_asset(docs, name, 256 * 1024)
        except (OSError, ValueError):
            raise RuntimeError(f'docs/{name}: the frozen case file the study names is missing or unreadable.') from None
        if hashlib.sha256(raw).hexdigest() != meta['sha256']:
            raise RuntimeError(f"docs/{name}: the frozen case file is not the study's bytes.")
        names.append(name)
    return tuple(names)


def public_files(root: Path) -> tuple[str, ...]:
    """Every file a reader's browser is asked for: index.html, each local asset
    it references -- its own modules AND the vendored design system -- and the
    records app.js fetches.

    Read off the page rather than kept in a tuple beside it, because a hand-kept
    list drifts in silence: it named six of the fourteen assets index.html
    loads, so the design system's own ``sc.css``, the burst map and the
    Following shelf were never fetched while the gate printed "Verified". A
    referenced file the checkout does not have is a 404 for every reader, so it
    is named and raises here rather than being skipped."""
    if (root / 'docs').is_symlink():
        raise RuntimeError('Publication docs root must not be a symlink.')
    references = re.findall(r"""(?:src|href)\s*=\s*["']([^"']+)["']""",
                            (root / "docs" / "index.html").read_text())
    names = ["index.html", *RECORD_FILES]
    # A new installation has no morning or research observation until its
    # first successful check. Once committed, each is part of the public-byte
    # acceptance gate.
    names.extend(name for name in OPTIONAL_RECORD_FILES if (root / "docs" / name).exists())
    for reference in references:
        name = reference.split("?", 1)[0].split("#", 1)[0]
        # A CDN, an absolute or protocol-relative URL, a bare fragment, and any
        # traversal are not files this checkout publishes.
        if not name or urlsplit(name).scheme or name.startswith(("/", "//")):
            continue
        if ".." in name.split("/") or name in names:
            continue
        names.append(name)
    absent = [name for name in names if not (root / "docs" / name).is_file()]
    if absent:
        raise RuntimeError("docs/ does not carry files the page asks readers to load: "
                           + ", ".join(absent))
    names.extend(name for name in reader_files(root) if name not in names)
    names.extend(name for name in issuer_files(root) if name not in names)
    names.extend(name for name in stop_research_files(root) if name not in names)
    names.extend(name for name in research_outcomes_files(root) if name not in names)
    names.extend(name for name in study_case_files(root) if name not in names)
    return tuple(names)


def github_api(repository: str, endpoint: str, method: str = "GET") -> dict:
    """Use the job's built-in token only with GitHub's own API via gh."""
    reply = subprocess.run(
        ["gh", "api", "--method", method, f"repos/{repository}/{endpoint}",
         "-H", "Accept: application/vnd.github+json"],
        check=False, capture_output=True, text=True, timeout=30,
    )
    if reply.returncode:
        # Do not copy an API response or credentials into a public log.
        raise RuntimeError(f"GitHub {method} {endpoint} failed (gh exit {reply.returncode}).")
    return json.loads(reply.stdout)


def public_bytes(url: str, timeout: float) -> bytes:
    # A fresh request carries no GitHub token, including on a custom domain.
    request = Request(url, headers={"Cache-Control": "no-cache"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def publish(repository: str, root: Path) -> None:
    files = public_files(root)
    expected = {name: hashlib.sha256((root / "docs" / name).read_bytes()).hexdigest()
                for name in files}
    site = github_api(repository, "pages")
    if site.get("build_type") != "legacy" or site.get("source") != {
        "branch": "main", "path": "/docs"
    }:
        raise RuntimeError("Pages must deploy from main /docs; no settings were changed.")
    base = site.get("html_url", "")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise RuntimeError("Pages did not return a usable HTTPS site URL.")

    queued = github_api(repository, "pages/builds", "POST")
    if queued.get("status") not in {"queued", "building", "built"}:
        raise RuntimeError("GitHub did not acknowledge a Pages build request.")
    print(f"Pages build requested; checking the {len(files)} files a reader loads.", flush=True)
    deadline = time.monotonic() + WAIT_SECONDS
    pending = list(files)
    while time.monotonic() < deadline:
        pending = []
        for name, digest in expected.items():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                pending.append(name)
                continue
            query = urlencode({"publication": digest, "attempt": time.monotonic_ns()})
            try:
                received = public_bytes(f"{base.rstrip('/')}/{name}?{query}", min(20, remaining))
                matches = hashlib.sha256(received).hexdigest() == digest
            except (OSError, TimeoutError, HTTPException):
                matches = False
            if not matches:
                pending.append(name)
        if not pending:
            print(f"Verified: every one of the {len(expected)} public files "
                  "matches committed main.")
            return
        print("Waiting for Pages: " + ", ".join(pending), flush=True)
        time.sleep(max(0, min(10, deadline - time.monotonic())))
    raise RuntimeError("Pages did not serve the committed files before the deadline: "
                       + ", ".join(pending) + ". The committed record remains in main.")


def main() -> int:
    try:
        repository = os.environ["GITHUB_REPOSITORY"]
        publish(repository, Path(__file__).resolve().parent.parent)
    except (KeyError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
