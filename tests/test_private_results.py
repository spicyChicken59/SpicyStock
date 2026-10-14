"""tools/private_results.py: the owner's reported results, re-derived from the
backup the page downloads and traced to the publication they came from (#110).

The backup under test is tests/fixtures/first-trade/backup.json, the exact
bytes the real page downloaded at the end of tools/first_trade_cases.mjs's
journey; page-results.json beside it is what the page printed. Every broker
fact in them is synthetic."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tools import private_results as pr

ROOT = Path(__file__).resolve().parent.parent
TRADE = ROOT / "tests" / "fixtures" / "first-trade"
CASH = ROOT / "tests" / "fixtures" / "cash-preview"
PAGE = ROOT / "tests" / "fixtures" / "page"
RESEARCH = ROOT / "tests" / "fixtures" / "stop-research"
BACKUP = (TRADE / "backup.json").read_bytes()
PRINTED = json.loads((TRADE / "page-results.json").read_text(encoding="utf-8"))
PUBLICATION = CASH / "publication-multiple.json"


def backup_with(mutate) -> bytes:
    store = json.loads(BACKUP)
    mutate(store)
    return json.dumps(store, separators=(",", ":")).encode("utf-8")


def record(reading, ticker):
    return next(row for row in reading["records"] if row["ticker"] == ticker)


def item_of(store, ticker):
    return next(item for item in store["items"] if item.get("plan", {}).get("ticker") == ticker)


# --- the rehearsal backup, as the page wrote it ------------------------------

def test_the_rehearsal_backup_is_bound_to_the_publication_it_was_prepared_from():
    sha = hashlib.sha256(PUBLICATION.read_bytes()).hexdigest()
    store = json.loads(BACKUP)
    assert store["version"] == 3 and len(store["items"]) == 2
    assert {item["publication"]["sha256"] for item in store["items"]} == {sha}, (
        "the cash-preview publication moved: regenerate the rehearsal with "
        "SCSTOCK_FIRST_TRADE_WRITE=1 node tools/page_smoke.mjs --only firsttrade")
    assert PRINTED["publication"] == "tests/fixtures/cash-preview/publication-multiple.json"


def test_every_record_traces_to_the_plan_its_publication_carries():
    reading = pr.read(BACKUP, pr.from_files([PUBLICATION]))
    for ticker in ("COIL", "AAPL"):
        trace = record(reading, ticker)["trace"]
        assert trace["status"] == "traced", trace
        assert trace["mismatches"] == [] and trace["session"] == "2026-09-10"


def test_the_reproduction_is_what_the_page_printed():
    reading = pr.read(BACKUP, None)
    store = json.loads(BACKUP)
    for ticker, printed in PRINTED["records"].items():
        row, item = record(reading, ticker), item_of(store, ticker)
        result, report = row["reported"], item["report"]
        amounts = {"Reported gross result": result["display"]["gross"],
                   "Reported actual costs": f"{result['display']['costs']} (entry ${report['entry_fees']} + exit ${report['exit_fees']})",
                   "Reported net result": result["display"]["net"]}
        if result["beyond_stop"]:
            beyond = result["beyond_stop"]
            share = "share" if beyond["quantity"] == 1 else "shares"
            amounts["Average exit below the published stop"] = (
                f"{beyond['display']['per_share']} a share · {beyond['display']['total']} on {beyond['quantity']} "
                f"reported {share} past the stop (a gap or slippage)")
        assert amounts == printed["amounts"], ticker
        assert result["outcome"] == printed["outcome"]
        assert row["draft"]["commitment"] == printed["draft_cash"]
        assert row["draft"]["risk_to_stop"] + " before fees, gaps and slippage" == printed["draft_risk"]


def test_the_figures_by_hand():
    reading = pr.read(BACKUP, None)
    coil, aapl = record(reading, "COIL"), record(reading, "AAPL")
    # COIL: 3 submitted, 2 filled at $111.05, 1 cancelled at the cutoff; out at
    # $113.20 and $114.00 (average $113.60); $0.02 of fees on the sales.
    assert coil["facts"]["submitted_quantity"] == 3 and coil["facts"]["filled_quantity"] == 2 and coil["facts"]["cancelled_quantity"] == 1
    assert (coil["reported"]["gross"], coil["reported"]["costs"], coil["reported"]["net"]) == ("5.100000", "0.020000", "5.080000")
    assert coil["reported"]["outcome"] == "gain" and coil["reported"]["beyond_stop"] is None
    # AAPL: 1 at $62.40; the stop at $60.70 filled at $59.85 on a gap down.
    assert (aapl["reported"]["gross"], aapl["reported"]["costs"], aapl["reported"]["net"]) == ("-2.550000", "0.010000", "-2.560000")
    assert aapl["reported"]["beyond_stop"]["per_share"] == "0.850000" and aapl["reported"]["beyond_stop"]["stop"] == "60.700000"
    assert reading["reported_totals"] == {"complete": 2, "net": "2.520000", "net_microusd": 2_520_000, "display": "$2.52"}
    # The drafts: 3 COIL at the $111.72 limit, 1 AAPL at $63.22, $1 of buffer each.
    assert coil["draft"] == {"quantity": 3, "published_quantity": 4, "principal": "$335.16", "fees_buffer": "$1.00",
                             "commitment": "$336.16", "risk_to_stop": "$6.66"}
    assert aapl["draft"]["commitment"] == "$64.22" and aapl["draft"]["risk_to_stop"] == "$2.52"


@pytest.mark.parametrize("exit_price, expected", [
    ("108.75", ("0.750000", "1.500000", "$0.75", "$1.50")),
    ("109.499999", ("0.000001", "0.000002", "<$0.01", "<$0.01")),
    ("109.5", None), ("109.500001", None),
])
def test_what_was_lost_past_the_stop_is_counted_on_every_reported_share(exit_price, expected):
    # COIL's two filled shares, both out under its $109.50 stop: a gap on both.
    def gapped(store):
        item_of(store, "COIL")["report"]["average_exit_price"] = exit_price
    beyond = record(pr.read(backup_with(gapped)), "COIL")["reported"]["beyond_stop"]
    if expected is None:
        assert beyond is None
    else:
        assert (beyond["per_share"], beyond["total"], beyond["display"]["per_share"], beyond["display"]["total"]) == expected
        assert beyond["quantity"] == 2 and beyond["stop"] == "109.500000"


def test_the_display_rounds_as_the_page_does():
    assert pr.display(0) == "$0.00" and pr.display(5_000) == "$0.01" and pr.display(4_999) == "<$0.01"
    assert pr.display(-1) == "-<$0.01" and pr.display(-5_000) == "-$0.01"
    assert pr.display(123_456_780_000) == "$123,456.78"
    assert pr.exact(-2_560_000) == "-2.560000" and pr.exact(1) == "0.000001"


def test_exact_beyond_safe_integers():
    def huge(store):
        item_of(store, "COIL")["report"].update(submitted_quantity=1000000, filled_quantity=1000000, cancelled_quantity=0, cancelled_at=None,
                                                 exited_quantity=1000000, average_price="0.000001", average_exit_price="9999999999.999999",
                                                 entry_fees="0.01", exit_fees="0.02", protected_quantity=None, protection_confirmed_at=None)
    result = record(pr.read(backup_with(huge)), "COIL")["reported"]
    # The page's own model test pins the same figures (tools/handoff_model_cases.mjs).
    assert result["gross_microusd"] == 9999999999999998000000 and result["net_microusd"] == 9999999999999997970000


# --- what is not a completed result ------------------------------------------

def test_a_partial_exit_has_no_figure_and_says_why():
    def partial(store):
        item_of(store, "COIL")["report"].update(exited_quantity=1, average_exit_price="113.2")
    result = record(pr.read(backup_with(partial)), "COIL")["reported"]
    assert result["state"] == "incomplete" and "net" not in result
    assert any("not fully exited" in reason for reason in result["reasons"])


@pytest.mark.parametrize("field", ["cancelled_quantity", "entry_fees", "exit_fees", "average_exit_price", "exited_at"])
def test_an_unknown_input_withholds_the_figure(field):
    def unknown(store):
        report = item_of(store, "AAPL")["report"]
        report[field] = None
    result = record(pr.read(backup_with(unknown)), "AAPL")["reported"]
    assert result["state"] == "incomplete" and field in result["missing"]


def test_an_unreconciled_remainder_withholds_the_figure():
    def unreconciled(store):
        item_of(store, "COIL")["report"].update(cancelled_quantity=0, cancelled_at=None)
    result = record(pr.read(backup_with(unreconciled)), "COIL")["reported"]
    assert result["state"] == "incomplete" and any("not reconciled" in reason for reason in result["reasons"])


# --- a backup the page would refuse is refused --------------------------------

def _set(ticker, **fields):
    return lambda store: item_of(store, ticker)["report"].update(fields)


@pytest.mark.parametrize("mutate, named", [
    (_set("COIL", filled_quantity=4), "filled plus cancelled exceeds submitted"),
    (_set("COIL", cancelled_quantity=2), "filled plus cancelled exceeds submitted"),
    (_set("COIL", exited_quantity=3), "exited exceeds filled"),
    (_set("COIL", average_price="111.050"), "average_price"),
    (_set("COIL", average_price="111.0500001"), "average_price"),
    (_set("COIL", average_price="0"), "average_price"),
    (_set("COIL", entry_fees="0.1"), "entry_fees"),
    (_set("COIL", filled_at="2026-09-11T13:33:40Z"), "filled_at"),
    (_set("COIL", filled_quantity=True), "filled_quantity"),
    (_set("AAPL", exited_at="2026-09-11T13:30:00.000Z"), "exited_at before the submission"),
    (_set("COIL", exited_quantity=0, exited_at=None), "an exit price without an exit"),
    (_set("COIL", submitted_quantity=None, submitted_at=None), "fills or cancellations without a submitted quantity"),
    (lambda s: item_of(s, "COIL").update(report_updated_at=None), "reported facts without a report clock"),
    (lambda s: item_of(s, "COIL").update(kind="broker_import"), "kind"),
    (lambda s: item_of(s, "COIL").update(extra=1), "record fields"),
    (lambda s: item_of(s, "COIL").update(id="0" * 64 + ":" + "1" * 64), "id"),
    (lambda s: item_of(s, "COIL")["draft"].update(quantity=5), "draft"),
    (lambda s: item_of(s, "COIL")["draft"].update(cash_cents=100), "draft"),
    (lambda s: item_of(s, "COIL")["plan"]["order"].update(limit_price=110.0), "plan.order"),
    (lambda s: item_of(s, "COIL")["plan"]["order"].update(limit_price=111.725), "plan.order"),
    (lambda s: item_of(s, "COIL")["plan"]["reference"].update(version=2), "plan.reference"),
    (lambda s: item_of(s, "COIL").update(created_at="2026-09-16T00:00:00.000Z"), "record clocks"),
    (lambda s: s["items"].append(copy.deepcopy(s["items"][0])), "share one identity"),
    (lambda s: s.update(version=4), "envelope"),
])
def test_a_record_the_page_would_refuse_is_refused_by_name(mutate, named):
    with pytest.raises(pr.Refused, match=named.replace("(", r"\(").replace(")", r"\)")):
        pr.read(backup_with(mutate))


def test_the_envelope_bounds():
    with pytest.raises(pr.Refused, match="byte-order mark"):
        pr.read(b"\xef\xbb\xbf" + BACKUP)
    with pytest.raises(pr.Refused, match="1 MiB"):
        pr.read(BACKUP + b" " * pr.MAX_BYTES)
    with pytest.raises(pr.Refused, match="not UTF-8 JSON"):
        pr.read(b"\xff\xfe")
    with pytest.raises(pr.Refused, match=f"more than {pr.MAX_ITEMS}"):
        pr.read(backup_with(lambda s: s["items"].extend([s["items"][0]] * pr.MAX_ITEMS)))


def test_a_legacy_store_is_read_as_the_page_normalizes_it():
    def legacy(store):
        store["version"] = 1
        for item in store["items"]:
            item["version"] = 1
            del item["kind"]
            for key in pr.RESULT_FIELDS:
                del item["report"][key]
    reading = pr.read(backup_with(legacy), pr.from_files([PUBLICATION]))
    assert reading["backup"]["version"] == 1
    # The legacy fields carried no exit price or fees: no figure, every record traced.
    assert all(row["reported"]["state"] == "incomplete" and row["trace"]["status"] == "traced" for row in reading["records"])


# --- the trace -----------------------------------------------------------------

@pytest.mark.parametrize("mutate, named", [
    (lambda s: item_of(s, "COIL")["plan"]["order"].update(limit_price=111.71), "plan.order"),
    (lambda s: item_of(s, "COIL")["plan"]["exit_schedule"][0].update(instruction="buy whenever"), "plan.exit_schedule"),
    (lambda s: item_of(s, "COIL")["plan"]["timing"].update(cutoff_at="2026-09-11T10:30:00-04:00"), "plan.timing"),
    (lambda s: item_of(s, "COIL")["publication"].update(rules_version="0" * 12), "publication.rules_version"),
    (lambda s: item_of(s, "COIL")["publication"].update(session="2026-09-09"), "publication.session"),
])
def test_a_frozen_plan_the_publication_does_not_carry_is_named(mutate, named):
    reading = pr.read(backup_with(mutate), pr.from_files([PUBLICATION]))
    assert record(reading, "COIL")["trace"] == {**record(reading, "COIL")["trace"], "status": "mismatch", "mismatches": [named]}
    assert record(reading, "AAPL")["trace"]["status"] == "traced"


def test_a_reference_the_publication_does_not_carry_is_named():
    def other(store):
        item = item_of(store, "COIL")
        item["plan"]["reference"]["pick_sha256"] = "0" * 64
    reading = pr.read(backup_with(other), pr.from_files([PUBLICATION]))
    assert record(reading, "COIL")["trace"]["mismatches"] == ["plan.reference"]


def test_a_publication_not_supplied_is_named_and_none_is_not_checked():
    reading = pr.read(BACKUP, pr.from_files([PAGE / "full.json"]))
    assert {row["trace"]["status"] for row in reading["records"]} == {"publication_not_found"}
    assert record(reading, "COIL")["trace"]["searched"] == 1
    assert {row["trace"]["status"] for row in pr.read(BACKUP, None)["records"]} == {"not_checked"}
    assert {row["model"]["status"] for row in pr.read(BACKUP, None)["records"]} == {"not_checked"}


# --- the model's own outcome, kept apart ---------------------------------------

def planned_from(path: Path, ticker: str, report: dict) -> dict:
    """A private record frozen from a published ticket, as the page's prepare()
    freezes it; its broker facts are the test's, synthetic."""
    raw = path.read_bytes()
    data = json.loads(raw)
    row = next(r for r in data["bursts"] if r["ticker"] == ticker)
    plan = row["plan"]
    sha = hashlib.sha256(raw).hexdigest()
    return {
        "version": 3, "kind": "planned_handoff", "id": sha + ":" + plan["evidence_ref"]["id"], "revision": 2,
        "created_at": "2026-09-11T13:35:00.000Z", "updated_at": "2026-09-11T20:00:00.000Z",
        "publication": {"sha256": sha, "session": data["run"]["session"], "published_at": data["run"]["published_at"],
                        "rules_version": data["app"]["rules_version"]},
        "plan": {"reference": plan["evidence_ref"], "ticker": ticker, "stage": "bursts", "order": plan["order_json"],
                 "timing": {k: data["run"]["timing"][k] for k in pr.TIMING_KEYS}, "exit_schedule": plan["exit_schedule"]},
        "draft": {"quantity": 1, "cash_cents": 200000, "fee_cents": 0},
        "report": {**{k: None for k in pr.LEGACY_FIELDS + pr.RESULT_FIELDS}, **report},
        "report_updated_at": "2026-09-11T20:00:00.000Z",
    }


AAPL_REPORT = {"submitted_quantity": 1, "submitted_at": "2026-09-11T13:31:00.000Z", "filled_quantity": 1, "average_price": "124.3",
               "filled_at": "2026-09-11T13:32:00.000Z", "cancelled_quantity": 0, "exited_quantity": 1, "exited_at": "2026-09-11T19:55:00.000Z",
               "average_exit_price": "121.4", "entry_fees": "0.00", "exit_fees": "0.01"}


def aapl_backup() -> bytes:
    return json.dumps({"version": 3, "items": [planned_from(PAGE / "full.json", "AAPL", AAPL_REPORT)]}).encode("utf-8")


def test_the_model_outcome_is_read_off_a_later_publication_and_never_added():
    reading = pr.read(aapl_backup(), pr.from_files([PAGE / "full.json", PAGE / "next.json"]))
    row = reading["records"][0]
    assert row["trace"]["status"] == "traced"
    model = row["model"]
    assert model["status"] == "observed" and model["session"] == "2026-09-11" and model["publication"].endswith("next.json")
    plan = model["plan"]
    assert (plan["status"], plan["fill"], plan["exit_price"], plan["result_pct"], plan["shares"]) == ("stopped", "filled at the open, $124.21", 121.42, -2.25, 4)
    # The owner's figure is the owner's: 1 share, $124.30 in, $121.40 out.
    assert row["reported"]["net"] == "-2.910000" and reading["reported_totals"]["net"] == "-2.910000"
    assert "Model" not in json.dumps(row["reported"]) and model["basis"].startswith("daily-bar model replay")


def test_no_later_publication_means_no_model_outcome():
    row = pr.read(aapl_backup(), pr.from_files([PAGE / "full.json"]))["records"][0]
    assert row["model"]["status"] == "not_observed"


def test_the_newest_publication_wins_and_a_later_argument_is_the_newer():
    # next and revised are one session, one clock; revised is the re-run on later bars.
    one = pr.read(aapl_backup(), pr.from_files([PAGE / "full.json", PAGE / "next.json", PAGE / "revised.json"]))["records"][0]["model"]
    two = pr.read(aapl_backup(), pr.from_files([PAGE / "full.json", PAGE / "revised.json", PAGE / "next.json"]))["records"][0]["model"]
    assert one["publication"].endswith("revised.json") and two["publication"].endswith("next.json")


# --- an independent research report ---------------------------------------------

def independent_backup(**report) -> tuple[bytes, list]:
    receipt = json.loads((RESEARCH / "current-receipt.json").read_text(encoding="utf-8"))
    bundle = json.loads((RESEARCH / "current-bundle.json").read_text(encoding="utf-8"))
    row = next(r for r in bundle["rows"] if r["ticker"] == "KE")
    source = {"ticker": "KE", "stage": "setting-up", "publication": receipt["publication"],
              "cohort": {"sha256": receipt["bundle"]["sha256"], "bytes": receipt["bundle"]["bytes"],
                         "generated_at": receipt["timing"]["generated_at"], "policy_id": receipt["policy"]["id"]},
              "evidence": row["evidence"], "baseline_admitted": row["baseline"]["admitted"]}
    item = {"version": 3, "kind": "independent_research", "id": receipt["publication"]["data_sha256"] + ":" + row["evidence"]["id"],
            "revision": 1, "created_at": "2026-10-12T15:00:00.000Z", "updated_at": "2026-10-12T15:00:00.000Z", "source": source,
            "report": {**{k: None for k in pr.LEGACY_FIELDS + pr.RESULT_FIELDS}, **report}, "report_updated_at": "2026-10-12T15:00:00.000Z"}
    publication = gzip.decompress((RESEARCH / "current-publication.json.gz").read_bytes())
    return json.dumps({"version": 3, "items": [item]}).encode("utf-8"), publication


def test_an_independent_report_traces_to_its_research_row_and_has_no_model(tmp_path):
    raw, publication = independent_backup(submitted_quantity=1, filled_quantity=1)
    (tmp_path / "data.json").write_bytes(publication)
    row = pr.read(raw, pr.from_files([tmp_path / "data.json"]))["records"][0]
    assert row["trace"]["status"] == "traced" and row["trace"]["mismatches"] == []
    assert row["model"]["status"] == "not_applicable" and row["draft"] is None and row["reported"]["state"] == "incomplete"
    tampered = json.loads(raw)
    tampered["items"][0]["source"]["evidence"]["plan_sha256"] = "0" * 64
    row = pr.read(json.dumps(tampered).encode(), pr.from_files([tmp_path / "data.json"]))["records"][0]
    assert row["trace"]["mismatches"] == ["source.evidence.plan_sha256"]


def test_an_independent_report_with_no_fill_clock_is_refused():
    raw, _ = independent_backup(submitted_quantity=1, filled_quantity=1)
    store = json.loads(raw)
    store["items"][0]["report_updated_at"] = None
    with pytest.raises(pr.Refused, match="report"):
        pr.read(json.dumps(store).encode())


# --- the history of docs/data.json, and the command ------------------------------

def git(repo: Path, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(repo)})


def test_the_history_of_docs_data_json_is_searched(tmp_path):
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    git(repo, "init", "-q")
    for name in ("full", "next"):
        (repo / "docs" / "data.json").write_bytes((PAGE / f"{name}.json").read_bytes())
        git(repo, "add", "docs/data.json")
        git(repo, "commit", "-q", "-m", name)
    (repo / "docs" / "other.txt").write_text("no record here")
    git(repo, "add", "docs/other.txt")
    git(repo, "commit", "-q", "-m", "unrelated")
    history = pr.from_git(repo)
    # Oldest first, so a later position is a newer commit.
    assert [(pub.position, pub.session) for pub in history] == [(0, "2026-09-10"), (1, "2026-09-11")]
    row = pr.read(aapl_backup(), history)["records"][0]
    assert row["trace"]["status"] == "traced" and row["model"]["status"] == "observed"
    assert len(pr.from_git(repo, limit=1)) == 1


def test_the_command(tmp_path, capsys):
    backup = tmp_path / "backup.json"
    backup.write_bytes(BACKUP)
    out = tmp_path / "reading.json"
    assert pr.main([str(backup), "--publication", str(PUBLICATION), "--json", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "traced to" in printed and "net $5.08" in printed and "net -$2.56" in printed and "loss on 1 share;" in printed
    assert json.loads(out.read_text(encoding="utf-8"))["reported_totals"]["display"] == "$2.52"
    assert pr.main([str(backup), "--publication", str(PAGE / "full.json")]) == 1
    assert pr.main([str(backup)]) == 0
    backup.write_bytes(b"\xef\xbb\xbf" + BACKUP)
    assert pr.main([str(backup)]) == 2
    assert "Nothing was re-derived" in capsys.readouterr().err


def test_the_tool_reads_and_writes_nothing_else(tmp_path, monkeypatch):
    """No network module is imported and nothing is written without --json."""
    import socket
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    backup = tmp_path / "backup.json"
    backup.write_bytes(BACKUP)
    before = sorted(p.name for p in tmp_path.iterdir())
    assert pr.main([str(backup), "--publication", str(PUBLICATION)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == before
