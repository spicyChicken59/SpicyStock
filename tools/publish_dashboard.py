"""Refresh branch-based Pages after a bot commit and verify what readers get.

GitHub documents that GITHUB_TOKEN pushes do not trigger Pages builds. The
publication workflow requests one explicitly, then checks every public file
against the committed checkout: the HTML, the two records, each script and
stylesheet the page loads, and the vendored design system it is drawn on. The
list is read off ``docs/index.html`` (``public_files``) so it cannot fall
behind the page. No market-data, scoring or delivery credentials are used, and
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


# The two records app.js fetches at run time. index.html does not link them,
# so they are the only public files that cannot be read off the page.
RECORD_FILES = ("data.json", "picks.json")
WAIT_SECONDS = 480


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
    references = re.findall(r"""(?:src|href)\s*=\s*["']([^"']+)["']""",
                            (root / "docs" / "index.html").read_text())
    names = ["index.html", *RECORD_FILES]
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
