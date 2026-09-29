"""Install the pinned official semantic validator without a shell installer.

Official rhysd/actionlint v1.7.12 release asset digests verified 2026-09-29:
https://github.com/rhysd/actionlint/releases/expanded_assets/v1.7.12
Digest verification establishes the reviewed release bytes; this installer does
not claim independently verified Sigstore provenance or modify the system PATH.
"""
from __future__ import annotations

import argparse
import hashlib
import io
from pathlib import Path
import platform
import tarfile
from urllib.request import urlopen
import zipfile

VERSION = "1.7.12"
SOURCE_COMMIT = "914e7df21a07ef503a81201c76d2b11c789d3fca"
ASSETS = {
    "Linux": ("linux_amd64.tar.gz", "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"),
    "Windows": ("windows_amd64.zip", "6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9"),
}


def install(destination: Path) -> Path:
    system = platform.system()
    if platform.machine().lower() not in {"amd64", "x86_64"} or system not in ASSETS:
        raise ValueError("unsupported_actionlint_platform")
    if destination.exists() or destination.is_symlink():
        raise ValueError("actionlint_destination_must_be_fresh")
    asset, expected = ASSETS[system]
    url = f"https://github.com/rhysd/actionlint/releases/download/v{VERSION}/actionlint_{VERSION}_{asset}"
    with urlopen(url, timeout=60) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("actionlint_release_digest_mismatch")
    member = "actionlint.exe" if system == "Windows" else "actionlint"
    if system == "Windows":
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            data = archive.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
            entry = archive.getmember(member)
            if not entry.isfile():
                raise ValueError("unexpected_actionlint_asset_member")
            data = archive.extractfile(entry).read()
    destination.mkdir(mode=0o700)
    output = destination / member
    with output.open("xb") as handle:
        handle.write(data)
    output.chmod(0o700)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    install(args.destination)
    print("PASS: pinned actionlint release installed")
