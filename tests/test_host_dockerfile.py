"""The morning host's Dockerfile carries nothing Railway's builder is known to refuse.

What these hold: no RUN --mount of any kind, no syntax directive, no build secret,
no VOLUME instruction, the exact install line and the supervisor as the
entrypoint. They do not show that Railway builds the file; only a deployment does.
"""
from pathlib import Path
import re

DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def text_of(path=DOCKERFILE):
    # utf-8-sig: Docker strips a byte-order mark before it reads a directive.
    return path.read_text(encoding="utf-8-sig")


def instructions(text):
    """The instructions Docker reads: comment lines dropped first, then continuations joined.

    Docker removes a comment line before it joins continuation lines, so a
    comment ending in a backslash does not swallow the instruction after it.
    """
    kept = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    joined = re.sub(r"\\[ \t]*\n", " ", kept)
    return [" ".join(line.split()) for line in joined.splitlines() if line.strip()]


def has_directive(text):
    return bool(re.search(r"^#\s*syntax\s*=", text, re.M | re.I))


def test_instructions_reads_the_file_as_docker_does():
    hidden = "FROM scratch\n# a note \\\nVOLUME /srv/spicystock\nRUN a \\\n  # inside\n  b\n"
    assert instructions(hidden) == ["FROM scratch", "VOLUME /srv/spicystock", "RUN a b"]
    assert has_directive("# syntax=docker/dockerfile:1\nFROM scratch\n")


def test_a_byte_order_mark_does_not_hide_a_directive(tmp_path):
    marked = tmp_path / "Dockerfile"
    marked.write_bytes("﻿# syntax=docker/dockerfile:1\nFROM scratch\n".encode("utf-8"))
    assert has_directive(text_of(marked))


def test_no_instruction_mounts_anything():
    # Railway refused the file that mounted a build secret (30 October 2026), and
    # accepts a cache mount only with an id this repository does not hard-code.
    assert not [i for i in instructions(text_of()) if "--mount" in i]


def test_no_frontend_directive_or_build_secret():
    text = text_of()
    assert not has_directive(text)
    assert "/run/secrets" not in text and "PIP_CERT" not in text


def test_no_volume_instruction():
    # The volume is Railway's, mounted at runtime; a VOLUME line is refused there.
    assert not [i for i in instructions(text_of()) if i.split()[0].upper() == "VOLUME"]


def test_the_exact_install_line_and_the_supervisor_entrypoint():
    steps = instructions(text_of())
    assert "RUN python -m pip install --no-cache-dir -r requirements-host.txt" in steps
    assert steps[-1] == 'ENTRYPOINT ["python", "-m", "src.morning_host"]'
