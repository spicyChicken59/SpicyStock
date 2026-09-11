"""Bonde's universe, offline: the transport it keeps and the policy it changes.

Every network boundary is a fake `requests.get` installed on the module, every
cache lives under tmp_path, and the seed file is a temporary one unless a test
says otherwise. Each rule below was deleted once and the test named for it
watched going red; the rejection tests assert the REASON WORD, so a row refused
by a different rule than the one named fails rather than passes.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from src import universe_v2 as universe

NOW = datetime(2026, 9, 11, 1, tzinfo=timezone.utc)
REAL_SEED = Path(__file__).resolve().parent.parent / "data" / "symbols.txt"


def sym(i: int) -> str:
    """A distinct three-letter ticker for index i."""
    return "".join(chr(65 + (i // 26 ** k) % 26) for k in (2, 1, 0))


def company(symbol: str = "NEW", **values) -> dict:
    return {"symbol": symbol, "name": "Example Inc. Common Stock", "country": "United States",
            "sector": "Technology", "industry": "Computer Software",
            "lastsale": "$20.00", "volume": "2000000", **values}


def listings(count: int = 500, *extra: dict) -> list[dict]:
    return [company(sym(i)) for i in range(count)] + list(extra)


def response(status: int = 200, rows: list | None = None, payload=None) -> requests.Response:
    reply = requests.Response()
    reply.status_code = status
    body = payload if payload is not None else {"data": {"rows": listings() if rows is None else rows}}
    reply._content = json.dumps(body).encode()
    return reply


class Endpoint:
    """A scripted api.nasdaq.com: each call takes the next outcome, the last repeats.

    An outcome is a Response, an exception instance, or an exception class
    (raised with a provider-shaped message, so a leak can be seen)."""

    def __init__(self, monkeypatch, *outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, dict]] = []
        self.pauses: list = []
        monkeypatch.setattr(universe.requests, "get", self)
        monkeypatch.setattr(universe.time, "sleep", self.pauses.append)

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, type) and issubclass(outcome, BaseException):
            raise outcome("provider-detail")
        return outcome


def cache_payload(rows: list[dict], fetched_at: datetime, **overrides) -> dict:
    payload = {"schema_version": universe.DIRECTORY_CACHE_SCHEMA, "source_url": universe.SOURCE_URL,
               "fetched_at": fetched_at.isoformat(), "rows": rows}
    payload.update(overrides)
    return payload


def write_cache(docs: Path, payload) -> Path:
    path = docs / universe.DIRECTORY_CACHE
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))
    return path


@pytest.fixture(autouse=True)
def seed_file(tmp_path, monkeypatch) -> Path:
    """A two-name seed, so no test reads data/symbols.txt by accident."""
    path = tmp_path / "symbols.txt"
    path.write_text("# reviewed\nAAPL\nMSFT  # trailing comment\n\n")
    monkeypatch.setattr(universe, "SEED_FILE", path)
    monkeypatch.delenv("SCAN_UNIVERSE", raising=False)
    return path


@pytest.fixture
def docs(tmp_path) -> Path:
    path = tmp_path / "docs"
    path.mkdir()
    return path


# ------------------------------------------------------------- transport ----


def test_the_request_sends_exactly_the_browser_headers_and_the_bounded_timeout(monkeypatch):
    """api.nasdaq.com holds a non-browser User-Agent open until the read times
    out, from every GitHub-hosted runner tried (probe run 34414747241): the
    former "SpicyStock/1.0 (...)", python-requests' default and the honest
    "Mozilla/5.0 (compatible; ...)" form each hung, while a Chrome-style
    string with a browser's Accept returned the directory in about a second.
    This pins the SHAPE that answered and the request to the constant."""
    endpoint = Endpoint(monkeypatch, response())
    assert len(universe.fetch_directory()) == 500
    (url, kwargs), = endpoint.calls
    assert url == universe.SOURCE_URL
    assert kwargs["headers"] == universe.DIRECTORY_HEADERS
    assert kwargs["timeout"] == universe.DIRECTORY_TIMEOUT == (5, 45)
    headers = universe.DIRECTORY_HEADERS
    assert set(headers) == {"User-Agent", "Accept"}
    agent = headers["User-Agent"]
    assert agent.startswith("Mozilla/5.0 (")
    assert all(token in agent for token in ("AppleWebKit/", "Chrome/", "Safari/"))
    assert not any(hung in agent for hung in ("compatible", "SpicyStock", "python-requests", "curl"))
    assert headers["Accept"] == "application/json, text/plain, */*"


@pytest.mark.parametrize("failure", [requests.ReadTimeout, requests.ConnectionError, 500, 502, 503, 504])
def test_a_transient_failure_is_retried_three_times_with_bounded_pauses(monkeypatch, failure):
    outcome = response(failure) if isinstance(failure, int) else failure
    endpoint = Endpoint(monkeypatch, outcome, outcome, response())
    assert len(universe.fetch_directory()) == 500
    assert len(endpoint.calls) == 3 and endpoint.pauses == [1, 3]
    assert universe.DIRECTORY_ATTEMPTS == 3 and universe.DIRECTORY_RETRY_PAUSES == (1, 3)


def test_three_transient_failures_raise_the_last_one_and_stop(monkeypatch):
    endpoint = Endpoint(monkeypatch, requests.ReadTimeout)
    with pytest.raises(requests.ReadTimeout):
        universe.fetch_directory()
    assert len(endpoint.calls) == 3 and endpoint.pauses == [1, 3]


@pytest.mark.parametrize("status", [401, 403, 404, 429])
def test_an_access_refusal_raises_at_once_without_a_retry(monkeypatch, status):
    endpoint = Endpoint(monkeypatch, response(status), response())
    with pytest.raises(requests.HTTPError):
        universe.fetch_directory()
    assert len(endpoint.calls) == 1 and endpoint.pauses == []
    assert status not in universe.TRANSIENT_STATUSES


@pytest.mark.parametrize("payload", [
    {"data": {"rows": listings(499)}},
    {"data": {"rows": "not a list"}},
    {"data": {}},
    {},
])
def test_a_directory_short_of_five_hundred_rows_is_refused(monkeypatch, payload):
    Endpoint(monkeypatch, response(payload=payload))
    with pytest.raises(ValueError, match="incomplete"):
        universe.fetch_directory()
    assert universe.DIRECTORY_MIN_ROWS == 500


def test_five_hundred_rows_is_the_floor_itself(monkeypatch):
    Endpoint(monkeypatch, response(rows=listings(500)))
    assert len(universe.fetch_directory()) == 500


# ----------------------------------------------------------------- cache ----


def test_a_live_directory_is_cached_and_read_back_until_it_expires(monkeypatch, docs):
    Endpoint(monkeypatch, response())
    live = universe.build(docs, now=NOW)
    assert live.source == universe.SOURCE_LIVE and live.warning is None
    assert live.fetched_at == NOW.isoformat()
    assert (docs / universe.DIRECTORY_CACHE).exists()

    Endpoint(monkeypatch, requests.ReadTimeout)
    cached = universe.build(docs, now=NOW + timedelta(days=1))
    assert cached.source == f"{universe.SOURCE_CACHE} 1.0 days old"
    assert cached.symbols == live.symbols and cached.fetched_at == NOW.isoformat()
    assert "captured 2026-09-11" in cached.warning and "seven days" in cached.warning

    edge = universe.build(docs, now=NOW + universe.DIRECTORY_MAX_AGE)
    assert edge.source.startswith(universe.SOURCE_CACHE), "a cache exactly seven days old is still valid"

    expired = universe.build(docs, now=NOW + universe.DIRECTORY_MAX_AGE + timedelta(seconds=1))
    assert expired.source == universe.SOURCE_SEED
    assert "within seven days" in expired.warning
    assert universe.DIRECTORY_MAX_AGE == timedelta(days=7)


def test_the_cache_keeps_only_the_fields_the_rules_read(monkeypatch, docs):
    Endpoint(monkeypatch, response(rows=listings(500, company("XTRA", marketCap="1,000", ipoyear="1999"))))
    universe.build(docs, now=NOW)
    stored = json.loads(gzip.decompress((docs / universe.DIRECTORY_CACHE).read_bytes()))
    assert stored["schema_version"] == universe.DIRECTORY_CACHE_SCHEMA == 1
    assert stored["source_url"] == universe.SOURCE_URL
    assert stored["fetched_at"] == NOW.isoformat()
    extra = next(row for row in stored["rows"] if row["symbol"] == "XTRA")
    assert tuple(extra) == universe.DIRECTORY_FIELDS


@pytest.mark.parametrize("damage", [
    "schema", "source_url", "naive_stamp", "future_stamp", "short", "missing_field", "not_gzip", "not_json",
])
def test_a_cache_that_is_not_the_one_this_code_wrote_is_refused(monkeypatch, docs, damage):
    rows = listings()
    payload = cache_payload(rows, NOW - timedelta(days=1))
    if damage == "schema":
        payload["schema_version"] = universe.DIRECTORY_CACHE_SCHEMA + 1
    if damage == "source_url":
        payload["source_url"] = universe.SOURCE_URL + "&extra=1"
    if damage == "naive_stamp":
        payload["fetched_at"] = (NOW - timedelta(days=1)).replace(tzinfo=None).isoformat()
    if damage == "future_stamp":
        payload["fetched_at"] = (NOW + timedelta(minutes=1)).isoformat()
    if damage == "short":
        payload["rows"] = rows[:499]
    if damage == "missing_field":
        payload["rows"] = rows[:-1] + [{k: v for k, v in rows[-1].items() if k != "volume"}]
    if damage == "not_gzip":
        (docs / universe.DIRECTORY_CACHE).write_bytes(b"not gzip at all")
    elif damage == "not_json":
        write_cache(docs, b"{not json")
    else:
        write_cache(docs, payload)
    Endpoint(monkeypatch, requests.ReadTimeout)
    built = universe.build(docs, now=NOW)
    assert built.source == universe.SOURCE_SEED and "within seven days" in built.warning


def test_a_storage_failure_does_not_discard_a_live_directory(monkeypatch, docs):
    Endpoint(monkeypatch, response())
    def refuse(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(universe, "_save_directory_cache", refuse)
    built = universe.build(docs, now=NOW)
    assert built.source == universe.SOURCE_LIVE and len(built.symbols) == 502
    assert not (docs / universe.DIRECTORY_CACHE).exists()


# -------------------------------------------------------- fallback order ----


def test_the_fallback_order_is_live_then_cache_then_seed(monkeypatch, docs):
    Endpoint(monkeypatch, response())
    assert universe.build(docs, now=NOW).source == universe.SOURCE_LIVE

    Endpoint(monkeypatch, requests.ConnectionError)
    assert universe.build(docs, now=NOW).source.startswith(universe.SOURCE_CACHE)

    (docs / universe.DIRECTORY_CACHE).unlink()
    seeded = universe.build(docs, now=NOW)
    assert seeded.source == universe.SOURCE_SEED and seeded.symbols == ["AAPL", "MSFT"]
    assert seeded.label == "2 checked-in US common stocks (data/symbols.txt)"
    assert seeded.warning and seeded.fetched_at is None


def test_a_refusal_or_a_bad_live_payload_never_borrows_the_cache(monkeypatch, docs):
    """An access refusal or an incomplete live reply is not a transport outage,
    so the fallback is the seed even while a valid cache sits on disk -- the
    rule the previous module set, kept as it was."""
    write_cache(docs, cache_payload(listings(), NOW - timedelta(days=1)))
    for bad in (response(403), response(rows=listings(499))):
        Endpoint(monkeypatch, bad)
        built = universe.build(docs, now=NOW)
        assert built.source == universe.SOURCE_SEED, bad.status_code
        assert built.warning and "captured" not in built.warning


def test_an_unexpected_error_falls_back_with_a_controlled_sentence(monkeypatch, docs):
    monkeypatch.setattr(universe, "fetch_directory", lambda: (_ for _ in ()).throw(RuntimeError("provider-detail")))
    built = universe.build(docs, now=NOW)
    assert built.source == universe.SOURCE_SEED
    assert "RuntimeError" in built.warning and "provider-detail" not in built.warning


# -------------------------------------------------------- classification ----


@pytest.mark.parametrize("values, reason", [
    ({"name": "iShares Core S&P 500 ETF"}, "not verified common stock"),
    ({"name": "STARWOOD PROPERTY TRUST INC. Starwood Property Trust Inc."}, "not verified common stock"),
    ({"name": "Issuer American Depositary Shares, each representing two Ordinary Shares"}, "not verified common stock"),
    ({"name": "Issuer 7.875% Series A Cumulative Preferred Stock"}, "not verified common stock"),
    ({"name": "Issuer Redeemable Warrants, each exercisable for one share of Class A Common Stock"}, "not verified common stock"),
    ({"name": "Issuer Units, each consisting of one share of Common Stock and one Warrant"}, "not verified common stock"),
    ({"name": "Issuer 5.875% Notes due 2059"}, "not verified common stock"),
    ({"name": "Nuveen Income Fund Common Shares of Beneficial Interest"}, "not verified common stock"),
    ({"name": ""}, "not verified common stock"),
    ({"name": "Visa Inc."}, "not verified common stock"),
    ({"name": "Issuer American Depositary Shares, each representing two Ordinary Shares", "country": "United Kingdom"},
     "not verified common stock"),
    ({"name": "CHS Inc Class B Cumulative Redeemable Preferred Stock Series 4"}, "not verified common stock"),
    ({"name": "Pennsylvania Real Estate Investment Trust Common Shares of Beneficial Interest"}, "not verified common stock"),
    ({"name": "abrdn Healthcare Investors Shares of Beneficial Interest"}, "not verified common stock"),
    ({"industry": "Blank Checks"}, "blank check company"),
    ({"industry": "blank checks"}, "blank check company"),
    ({"industry": ""}, "unknown industry"),
    ({"sector": ""}, "unknown industry"),
    ({"symbol": "BRK.B"}, "symbol format"),
    ({"symbol": "ABR^D"}, "symbol format"),
    ({"symbol": "abc"}, "symbol format"),
    ({"symbol": "TOOLONG"}, "symbol format"),
    ({"symbol": 7}, "symbol format"),
    ({"lastsale": "$2.99"}, "price under $3"),
    ({"lastsale": ""}, "price under $3"),
    ({"lastsale": "n/a"}, "price under $3"),
    ({"volume": "99,999"}, "volume under 100,000 shares"),
    ({"volume": "99999"}, "volume under 100,000 shares"),
    ({"volume": ""}, "volume under 100,000 shares"),
])
def test_each_exclusion_refuses_for_the_reason_it_names(values, reason):
    row = company(**values)
    assert universe.classify(row, set()) == reason
    symbols, names, flags, counts = universe.admit([row], [])
    assert symbols == [] and names == {} and flags == {}
    assert counts == {"listed": 1, reason: 1, "admitted": 0}


def test_a_plain_us_common_stock_is_admitted_with_no_flag():
    assert universe.classify(company(), set()) is None
    symbols, names, flags, counts = universe.admit([company("ACME", name="Acme Corp. Class A Common Stock")], [])
    assert symbols == ["ACME"] and names == {"ACME": "Acme Corp. Class A Common Stock"}
    assert flags == {"ACME": set()} and counts == {"listed": 1, "admitted": 1}


@pytest.mark.parametrize("values", [
    {"industry": "Biotechnology: Pharmaceutical Preparations"},
    {"industry": "Biotechnology: Laboratory Analytical Instruments", "sector": "Industrials"},
    {"industry": "Medicinal Chemicals and Botanical Products"},
    {"sector": "Health Care", "industry": "Medical/Dental Instruments"},
])
def test_biotech_and_health_care_are_admitted_and_flagged_never_refused(values):
    """Bonde has no sector exclusion; the flag is a warning for the page, and
    Nasdaq's "Biotechnology:" prefix reaches non-biotech industries too."""
    row = company("BIO", **values)
    assert universe.classify(row, set()) is None
    symbols, names, flags, counts = universe.admit([row], [])
    assert symbols == ["BIO"] and flags == {"BIO": {universe.BIOTECH_FLAG}}
    assert counts == {"listed": 1, "admitted": 1}
    assert universe.BIOTECH_FLAG == "biotech"


def test_the_flag_reads_both_the_sector_and_the_industry():
    assert universe.flags_for(company(sector="Health Care", industry="Other")) == {"biotech"}
    assert universe.flags_for(company(sector="Industrials", industry="Biotechnology: Instruments")) == {"biotech"}
    assert universe.flags_for(company(sector="Industrials", industry="Aluminum")) == set()
    assert universe.flags_for(company(country="Israel", sector="Health Care")) == {"biotech", "foreign"}


@pytest.mark.parametrize("values", [
    {"name": "Shopify Inc. Class A Subordinate Voting Shares", "country": "Canada"},
    {"name": "Ardagh Metal Packaging S.A. Ordinary Shares", "country": "Luxembourg"},
    {"name": "lululemon athletica inc. Common Stock", "country": "Canada"},
    {"name": "Applied Aerospace & Defense Inc. Common Stock", "country": ""},
])
def test_a_foreign_domiciled_common_share_is_admitted_with_the_foreign_flag(values):
    """Bonde's TC2000 list does not exclude US-listed shares of foreign-domiciled
    companies, so the country is a flag. A blank country carries it too: the
    directory then vouches for no domicile at all."""
    row = company("FRGN", **values)
    assert universe.classify(row, set()) is None
    symbols, names, flags, counts = universe.admit([row], [])
    assert symbols == ["FRGN"] and flags == {"FRGN": {universe.FOREIGN_FLAG}}
    assert counts == {"listed": 1, "admitted": 1}
    assert universe.FOREIGN_FLAG == "foreign"


def test_a_depositary_receipt_is_still_refused_whatever_its_country():
    """The domicile stopped refusing; the receipt did not. This name matches
    `_NAME` through "Ordinary Shares", so only `_REJECT` stands between it and
    the universe."""
    for country in ("United Kingdom", "United States", ""):
        row = company("ADR", name="Issuer American Depositary Shares, each representing two Ordinary Shares",
                      country=country)
        assert universe.classify(row, set()) == "not verified common stock", country
        assert universe.admit([row], [])[0] == []


@pytest.mark.parametrize("name", [
    "Zillow Group Inc. Class C Capital Stock",
    "Alphabet Inc. Class C Capital Stock",
    "Acme Holdings Capital Stock",
    "Eastman Kodak Company Common New",
    "Brookfield Renewable Corporation Class A Subordinate Voting Shares",
    "Acme Corp. Common Stock, par value $0.01",
])
def test_a_common_share_named_without_the_words_common_stock_is_admitted(name):
    """Each pattern has a case only IT admits: "Acme Holdings Capital Stock"
    carries no class, so dropping `capital stock` is red here even though the
    two real Class C names would still enter through the class pattern."""
    row = company("NYSE", name=name)
    assert universe.classify(row, set()) is None
    assert universe.admit([row], [])[0] == ["NYSE"]


def test_shares_of_beneficial_interest_are_a_trust_and_refused():
    """A REIT or closed-end trust lists "Common Shares of Beneficial Interest",
    which the common-share wording alone would admit."""
    for name in ("Pennsylvania Real Estate Investment Trust Common Shares of Beneficial Interest",
                 "BlackRock Science and Technology Trust Common Shares of Beneficial Interest",
                 "abrdn Healthcare Investors Shares of Beneficial Interest"):
        assert universe.classify(company("REIT", name=name), set()) == "not verified common stock", name
    assert universe.classify(company("REIT", name="Acme REIT Inc. Common Stock"), set()) is None


def test_the_floors_are_bondes_numbers_and_inclusive_at_the_edge():
    assert universe.MIN_PRICE == 3.0 and universe.MIN_VOLUME == 100_000
    assert universe.classify(company(lastsale="$3.00"), set()) is None
    assert universe.classify(company(lastsale="$2.99"), set()) == "price under $3"
    assert universe.classify(company(volume="100,000"), set()) is None
    assert universe.classify(company(volume="100000"), set()) is None
    assert universe.classify(company(volume="99,999"), set()) == "volume under 100,000 shares"


def test_seed_names_are_admitted_whether_or_not_the_directory_lists_them(monkeypatch, docs, seed_file):
    seed_file.write_text("AAPL\nMSFT\nZZZZ\n")
    rows = listings(500, company("AAPL", name="Apple Inc. Common Stock"),
                    company("MSFT", name="Microsoft Corporation", sector="Health Care", lastsale="$1.00"))
    Endpoint(monkeypatch, response(rows=rows))
    built = universe.build(docs, now=NOW)
    assert {"AAPL", "MSFT", "ZZZZ"} <= set(built.symbols)
    assert built.counts["admitted"] == 503 and built.counts[universe.SEED_EXCEPTION] == 2
    assert built.names["AAPL"] == "Apple Inc. Common Stock" and built.names["MSFT"] == "Microsoft Corporation"
    assert "ZZZZ" not in built.names
    assert built.flags["MSFT"] == {"biotech"} and built.flags["ZZZZ"] == set() and built.flags["AAPL"] == set()


def test_a_seed_name_the_rules_would_admit_anyway_is_not_an_exception(monkeypatch, docs):
    """The exception count is what the seed BOUGHT: a name the directory would
    have admitted on its own does not count. The first version counted every
    seed, because its probe replaced the symbol with one the regex refuses."""
    Endpoint(monkeypatch, response(rows=listings(500, company("AAPL"), company("MSFT"))))
    built = universe.build(docs, now=NOW)
    assert universe.SEED_EXCEPTION not in built.counts
    assert built.counts["admitted"] == 502


def test_the_counts_add_up_to_what_was_listed_plus_the_seeds_the_directory_lacked(monkeypatch, docs, seed_file):
    seed_file.write_text("AAPL\nMSFT\nZZZZ\nYYYY\n")
    rows = listings(500, company("AAPL"), company("MSFT", lastsale="$1"),
                    company(name="Some Trust ETF"), company("CANA", country="Canada"), company(industry="Blank Checks"),
                    company(industry=""), company(lastsale="$2"), company(volume="5"), company(symbol="BRK.B"),
                    "not a row at all")
    Endpoint(monkeypatch, response(rows=rows))
    built = universe.build(docs, now=NOW)
    exclusions = {k: v for k, v in built.counts.items() if k not in {"listed", "admitted", universe.SEED_EXCEPTION}}
    assert built.counts["listed"] == 509, "a row that is not an object is not a listing"
    assert set(exclusions) == {"not verified common stock", "blank check company",
                               "unknown industry", "price under $3", "volume under 100,000 shares", "symbol format"}
    assert built.counts["admitted"] + sum(exclusions.values()) == built.counts["listed"] + 2
    assert built.counts[universe.SEED_EXCEPTION] == 3
    assert "CANA" in built.symbols and built.flags["CANA"] == {"foreign"}, "a domicile is a flag, not a cut"


# ------------------------------------------------------------ overrides ----


def test_the_explicit_override_asks_nothing_of_the_network(monkeypatch, docs):
    monkeypatch.setattr(universe.requests, "get", lambda *a, **k: pytest.fail("the directory must not be fetched"))
    built = universe.build(docs, explicit=["msft", " AAPL", "aapl"])
    assert built.symbols == ["AAPL", "MSFT"] and built.source == universe.SOURCE_EXPLICIT
    assert built.label == "2 named on the command line (--tickers)"
    assert built.counts == {"admitted": 2} and built.fetched_at is None and built.warning is None
    assert built.flags == {"AAPL": set(), "MSFT": set()} and built.names == {}
    for bad in (["BRK.B"], ["AAPL", "toolong"], [], [""]):
        with pytest.raises(ValueError):
            universe.build(docs, explicit=bad)


@pytest.mark.parametrize("value, expected", [
    ("adaptive", "directory"), ("directory", "directory"), ("seed", "seed"),
    ("", "directory"), (" Seed ", "seed"), ("ADAPTIVE", "directory"),
])
def test_scan_universe_accepts_the_old_spelling_and_the_new(monkeypatch, value, expected):
    monkeypatch.setenv("SCAN_UNIVERSE", value)
    assert universe.mode() == expected
    assert universe.enabled() == (expected == "directory")


def test_an_unset_scan_universe_means_the_directory_and_a_typo_is_an_error(monkeypatch):
    assert universe.mode() == "directory" and universe.enabled()
    monkeypatch.setenv("SCAN_UNIVERSE", "adpative")
    with pytest.raises(ValueError, match="SCAN_UNIVERSE"):
        universe.mode()


def test_seed_mode_reads_the_file_alone_and_never_fetches(monkeypatch, docs):
    monkeypatch.setenv("SCAN_UNIVERSE", "seed")
    monkeypatch.setattr(universe.requests, "get", lambda *a, **k: pytest.fail("the directory must not be fetched"))
    built = universe.build(docs, now=NOW)
    assert built.symbols == ["AAPL", "MSFT"] and built.source == universe.SOURCE_SEED
    assert built.warning is None and built.counts == {"admitted": 2}
    assert built.label == "2 checked-in US common stocks (data/symbols.txt)"


# ------------------------------------------------------------ the bound ----


def test_max_discovery_is_a_safety_bound_reported_when_it_binds(monkeypatch, docs, seed_file):
    """Bonde's list is ~6,500 and the September 2026 directory admits ~2,600,
    so 8000 binds only on an endpoint that grew past anything seen; when it
    does, the least-liquid tail goes, the seed never does, and the warning
    says so."""
    assert universe.MAX_DISCOVERY == 8000
    seed_file.write_text("AAA\n")
    rows = [company(sym(i), lastsale="$10.00", volume=str(100_000 * (i + 1))) for i in range(8)]
    rows[0]["lastsale"] = "$3.00"  # AAA: the thinnest name of all, and a seed
    monkeypatch.setattr(universe, "MAX_DISCOVERY", 5)
    monkeypatch.setattr(universe, "DIRECTORY_MIN_ROWS", 1)
    Endpoint(monkeypatch, response(rows=rows))
    built = universe.build(docs, now=NOW)
    assert built.symbols == sorted(["AAA"] + [sym(i) for i in (4, 5, 6, 7)])
    assert built.counts[universe.CAPACITY_REASON] == 3 and built.counts["admitted"] == 5
    assert "MAX_DISCOVERY bound: 3 least-liquid names cut at 5" in built.warning
    assert set(built.names) == set(built.symbols) == set(built.flags)

    monkeypatch.setattr(universe, "MAX_DISCOVERY", 8)
    Endpoint(monkeypatch, response(rows=rows))
    relaxed = universe.build(docs, now=NOW)
    assert len(relaxed.symbols) == 8 and universe.CAPACITY_REASON not in relaxed.counts
    assert relaxed.warning is None


# -------------------------------------------------------------- identity ----


def test_identity_is_order_independent_and_pinned_to_the_digest():
    expected = hashlib.sha256(b"AAPL\nMSFT").hexdigest()[:16]
    assert universe.identity(["MSFT", "AAPL"]) == universe.identity(["AAPL", "MSFT"]) == expected
    assert universe.identity(["AAPL"]) != expected
    built = universe.build(Path("unused"), explicit=["MSFT", "AAPL"])
    assert built.identity == expected


# ----------------------------------------------------------------- seed ----


def test_the_real_seed_file_parses_and_a_typo_refuses_the_run(tmp_path):
    real = universe.read_seed(REAL_SEED)
    assert len(real) >= 100 and len(set(real)) == len(real)
    assert all(universe._SYMBOL.fullmatch(s) for s in real)
    for text in ("brk.b\n", "AAPL\nAAPL\n", "# nothing but comments\n", "TOOLONG\n"):
        (tmp_path / "bad.txt").write_text(text)
        with pytest.raises(universe.SymbolFileError):
            universe.read_seed(tmp_path / "bad.txt")
    with pytest.raises(universe.SymbolFileError, match="cannot read"):
        universe.read_seed(tmp_path / "absent.txt")


def test_the_label_names_the_source_the_floors_and_the_flag_count(monkeypatch, docs):
    rows = listings(500, company("BIO", industry="Biotechnology: Pharmaceutical Preparations"),
                    company("SHOP", country="Canada"), company("TEVA", country="Israel", sector="Health Care"))
    Endpoint(monkeypatch, response(rows=rows))
    built = universe.build(docs, now=NOW)
    assert built.label == ("505 US-listed common stocks from the Nasdaq directory 2026-09-11, "
                           "$3+ and 100,000+ shares last session (2 flagged biotech, 2 flagged foreign)")
    Endpoint(monkeypatch, requests.ReadTimeout)
    cached = universe.build(docs, now=NOW + timedelta(days=2))
    assert cached.label.startswith("505 US-listed common stocks from the Nasdaq directory captured 2026-09-11, ")
