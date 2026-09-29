"""Install only the reviewed official age release into a fresh tools directory.

Release asset digests were checked against FiloSottile/age's GitHub release API
on 2026-09-28. No installer, shell pipe, elevated install or PATH edit is used.
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

VERSION = "v1.3.2"
SOURCE_COMMIT = "b74dce4cdbe35b5e5f66c06d9612b72f89028758"
ASSETS = {
    "Linux": ("linux-amd64.tar.gz", "cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10"),
    "Windows": ("windows-amd64.zip", "f48d8f8f9ebe903ab5027ed067652f2cc1db94bc206976430133b905dcd8e8c7"),
}


def install(destination: Path) -> Path:
    system = platform.system()
    if platform.machine().lower() not in {"amd64", "x86_64"} or system not in ASSETS:
        raise ValueError("unsupported_age_platform")
    if destination.exists() or destination.is_symlink():
        raise ValueError("age_destination_must_be_fresh")
    asset, expected = ASSETS[system]
    url = f"https://github.com/FiloSottile/age/releases/download/{VERSION}/age-{VERSION}-{asset}"
    with urlopen(url, timeout=60) as response:
        raw = response.read(32 * 1024 * 1024 + 1)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("age_release_digest_mismatch")
    suffix = ".exe" if system == "Windows" else ""
    destination.mkdir(mode=0o700)
    for name in ("age", "age-keygen"):
        member = "age/" + name + suffix
        if system == "Windows":
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                data = archive.read(member)
        else:
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
                entry = archive.getmember(member)
                if not entry.isfile():
                    raise ValueError("unexpected_age_asset_member")
                data = archive.extractfile(entry).read()
        output = destination / (name + suffix)
        with output.open("xb") as handle:
            handle.write(data)
        output.chmod(0o700)
    return destination / ("age" + suffix)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    install(args.destination)
    print("PASS: pinned age release installed")
