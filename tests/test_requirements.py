"""Every direct requirement a run installs is held below its next major, or
pinned; their own dependencies are resolved by pip within the ranges those
packages declare, and only requirements-host.txt pins the full set.

PyPI is part of the environment: anthropic 2.0.0, published on 21 Oct 2026,
changed the API version the SDK sends and every chart read of two nights failed
with no change in this repository. A bound is raised in its own change, with
the suite run against the new major.
"""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r"(?P<name>[A-Za-z0-9_.\-]+)\s*(?P<spec>.*)\Z")


def requirements(name):
    out = []
    for raw in (ROOT / name).read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-r "):
            out.append(LINE.fullmatch(line).groupdict())
    return out


@pytest.mark.parametrize("name", ["requirements.txt", "requirements-dev.txt", "requirements-host.txt"])
def test_each_requirement_is_bounded_above_or_pinned(name):
    found = requirements(name)
    assert found, name
    for req in found:
        clauses = [c.strip() for c in req["spec"].split(",") if c.strip()]
        pinned = len(clauses) == 1 and clauses[0].startswith("==")
        bounded = any(c.startswith(">=") for c in clauses) and any(re.fullmatch(r"<\s*[0-9][0-9.]*", c) for c in clauses)
        assert pinned or bounded, f"{name}: {req['name']}{req['spec']} has no upper bound"


def test_the_bounds_name_the_majors_the_suite_was_run_against():
    bounds = {r["name"].lower(): r["spec"].replace(" ", "") for r in requirements("requirements.txt") + requirements("requirements-dev.txt")}
    assert bounds == {
        "pandas": ">=2.0,<4", "numpy": ">=1.24,<3", "requests": ">=2.31,<3", "mplfinance": ">=0.12.10b0,<0.13",
        "anthropic": ">=1.15,<2", "resend": ">=2.0,<3", "alpaca-py": ">=0.21,<1", "exchange_calendars": "==4.13.2",
        "pytest": ">=8.0,<10", "httpx2": ">=2.12,<3", "pyyaml": ">=6.0,<7"}
