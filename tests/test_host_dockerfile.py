"""The morning host's Dockerfile builds on Railway: no RUN --mount, no syntax directive."""
from pathlib import Path
import re

DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def instructions():
    joined = re.sub(r"\\\n", " ", DOCKERFILE.read_text())
    return [line.strip() for line in joined.splitlines() if line.strip() and not line.strip().startswith("#")]


def test_no_instruction_mounts_anything_railway_refuses():
    # Railway refused the file that mounted a build secret (31 October 2026).
    assert not [i for i in instructions() if "--mount" in i]


def test_no_frontend_directive_or_build_secret():
    text = DOCKERFILE.read_text()
    assert not re.search(r"^#\s*syntax\s*=", text, re.M | re.I)
    assert "/run/secrets" not in text and "PIP_CERT" not in text


def test_the_image_still_installs_the_host_pins_and_starts_the_supervisor():
    steps = instructions()
    assert "RUN python -m pip install --no-cache-dir -r requirements-host.txt" in steps
    assert steps[-1] == 'ENTRYPOINT ["python", "-m", "src.morning_host"]'
