"""The recorded reaction admission, separate from subsequent chart quality.

This describes the scanner's decision; it does not rerun it or revise an old
record. Archived callers must supply that record's rules, never today's rules.
"""
from __future__ import annotations

from copy import deepcopy
import re

from src import scans

VERSION = 1
RULES = {"grading.discovery_version": VERSION}
ROUTES = {"burst": ("burst",), "dollar": ("dollar",), "both": ("burst", "dollar")}
FIELDS = ("close", "prev_close", "open", "gain_pct", "volume", "prev_volume",
          "volume_vs_prior", "dollar_move")
RULE_KEYS = {
    "burst": ("min_ratio", "volume_above_prior", "min_volume"),
    "dollar": ("min_move", "min_volume_exclusive"),
}


def contract(row: dict, rules: dict | None = None) -> dict:
    """One deterministic contract for live rows and archived-input replays.

    Missing historical measurements stay null (especially prior volume); a
    rounded volume ratio cannot recover exact shares. Thresholds are copied
    from RULES or the supplied nested archive, with no historical defaults.
    """
    admitted = ROUTES[row["scan"]]
    source = scans.RULES if rules is None else rules
    families = {family: {key: deepcopy(source[f"{family}.{key}"] if rules is None
                                      else source[family][key]) for key in keys}
                for family, keys in RULE_KEYS.items()}
    return {
        "version": VERSION,
        "admitted_by": list(admitted),
        "applicable_rules": {k: v for k, v in families.items() if k in admitted},
        "inapplicable_rules": {k: v for k, v in families.items() if k not in admitted},
        "measurements": {k: deepcopy(row.get(k)) for k in FIELDS},
    }


def for_metrics(metrics: dict) -> dict | None:
    """Use the scanner's block unchanged; support explicit archived replays."""
    if "discovery" in metrics:
        block = metrics["discovery"]
        if (block["version"] != VERSION or
                block["admitted_by"] != list(ROUTES[metrics["scan"]]) or
                set(block["applicable_rules"]) != set(block["admitted_by"]) or
                set(block["inapplicable_rules"]) != set(RULE_KEYS) - set(block["admitted_by"])):
            raise ValueError("discovery identity disagrees with candidate")
        for family, rules in {**block["applicable_rules"], **block["inapplicable_rules"]}.items():
            if set(rules) != set(RULE_KEYS[family]):
                raise ValueError("discovery rule fields disagree with route")
        return block
    if "scan" in metrics:
        return contract(metrics, metrics.get("recorded_rules"))
    return None  # transport-only callers; the reaction pipeline always supplies it


def instruction(block: dict | None) -> str:
    if block is None:
        return ""
    routes = ", ".join(block["admitted_by"])
    return (f"This candidate was admitted by {routes}. Discovery is already established. "
            "The discovery.applicable_rules describe that admission; "
            "discovery.inapplicable_rules are NOT admission requirements. "
            "Do not substitute another route's minimum or volume condition. "
            "Judge quality from the chart and checklist after discovery; scan identity "
            "alone makes a setup neither stronger nor weaker. "
            "Any lowering must name independent measured or visible quality evidence.\n\n")


def conflicting_fields(block: dict | None, reply: dict) -> list[str]:
    """Conservative tripwire for explicit alternative-threshold rejection.

    This is NOT a semantic correctness certificate. The history audit includes
    manual review of every model row, including claims without numeric words.
    Reject the whole reply, never silently excise a reason and keep its score.
    """
    if not block or not block["inapplicable_rules"]:
        return []
    other = block["inapplicable_rules"]
    if "burst" in other:
        pct = round((other["burst"]["min_ratio"] - 1) * 100, 8)
        number = re.escape(f"{pct:g}") + r"(?:\.0+)?\s*(?:%|percent)"
        if pct == 4:
            number = rf"(?:{number}|four[ -]percent)"
        threshold = rf"(?<![\d.]){number}"
    else:
        amount = other["dollar"]["min_move"]
        threshold = rf"(?:\$\s*{re.escape(f'{amount:g}')}0*|{re.escape(f'{amount:g}')}0*\s*dollars?)"
    rejection = r"minimum|threshold|requir\w*|below|under|sub[- ]|fail\w*|does not meet|did not meet"
    bad = []
    for field in ("reason", "key_risk", "entry_note"):
        # Don't split decimal numbers into sentences.
        for sentence in re.split(r"(?<=[.!?])\s+", str(reply.get(field, "")).lower()):
            # The earlier ADP revision omits the number four altogether: it
            # declares the small percent gain itself disqualifying under ANY
            # reading. Keep this reviewed construction distinct from a visual
            # critique of a small bar or a weak bounce.
            if "burst" in other and re.search(
                    r"\bgains?\s+only\s+[\d.]+\s*%\s*[—–-]\s*not a (?:momentum )?burst by any reading", sentence):
                bad.append(field)
                break
            matches = list(re.finditer(threshold, sentence))
            if "burst" in other:
                matches = [m for m in matches if not re.match(r"\s+(?:down|breakdown)", sentence[m.end():])]
            # The plan also has percent stop/entry limits. They are not scan
            # admission: don't quarantine a correctly stated risk instruction.
            admission = re.search(r"gain|close.to.close|momentum|range.expansion|"
                                  r"(?:burst|discovery|admission)\s+(?:minimum|threshold|criteria|rule)", sentence)
            if re.search(r"\bstop\b|\brisk\b|ceiling|entry limit", sentence) and not admission:
                continue
            if matches and re.search(rejection, sentence):
                # A 4% DOWN day in a base is a quality measurement, not today's
                # close-to-close UP admission. Preserve that legitimate use.
                bad.append(field)
                break
    return bad
