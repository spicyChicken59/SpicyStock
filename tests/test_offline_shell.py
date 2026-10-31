"""Every offline check reads the page shell with its morning endpoint blanked.

The committed shell (docs/index.html) names the deployed morning receipt
endpoint. A tool that serves files from the checkout, or builds a DOM from the
shell, would otherwise read the live service in place of its fixtures -- the
publication-recovery suite did, on 31 October 2026, and timed out waiting for a
fixture receipt it never read. Each such tool must pass the shell through
tools/offline_shell.mjs, or say here why it never serves the shell."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
#: tools that run a server or a DOM and never serve docs/index.html, with the reason
NEVER_SERVE_THE_SHELL = {
    "chart_check.mjs": "serves its own chart harness page, never the site shell",
}
STARTS = re.compile(r"\bcreateServer\(|\bnew JSDOM\(")
BLANKS = re.compile(r"\boffline\(|\bwithEndpoint\(")


def harnesses():
    return sorted(p for p in TOOLS.glob("*.*js") if STARTS.search(p.read_text(encoding="utf-8")))


def test_every_server_or_dom_check_blanks_the_shells_endpoint():
    found = {p.name for p in harnesses()}
    assert found >= {"page_smoke.mjs", "publication_recovery_cases.mjs", "check_decision_inspection.mjs",
                     "continuity_check.mjs", "evidence_focus_cases.mjs"}, found
    missing = [p.name for p in harnesses()
               if p.name not in NEVER_SERVE_THE_SHELL and not BLANKS.search(p.read_text(encoding="utf-8"))]
    assert missing == [], f"serves or builds the page shell without blanking its live endpoint: {missing}"


def test_the_exemptions_are_still_true():
    for name, why in NEVER_SERVE_THE_SHELL.items():
        text = (TOOLS / name).read_text(encoding="utf-8")
        assert STARTS.search(text), f"{name} no longer runs a server or a DOM: drop its exemption"
        assert "index.html" not in text, f"{name} reads index.html now, so its exemption ({why}) is no longer true"


def test_the_helper_blanks_and_sets_the_tag():
    helper = (TOOLS / "offline_shell.mjs").read_text(encoding="utf-8")
    assert 'meta name="spicystock-morning-endpoint" content="' in helper
    shell = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    assert shell.count('<meta name="spicystock-morning-endpoint" content="') == 1, \
        "the shell's endpoint tag must be spelled as the helper matches it, once"
