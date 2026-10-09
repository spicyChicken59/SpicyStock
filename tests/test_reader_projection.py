"""Exact transport derivation, bounded retention and real publication failures."""
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from src import reader
from tests.test_pipeline import evening, market, claude


def canonical(*, email="pending", legacy=False):
    observations = {"as_of": "2026-10-08", "days": 21, "symbols": {
        "OLD": {"date": "2026-10-08", "c": 12.0, "since": "2026-09-21",
                "history": [{"date": "2026-10-07", "c": 11.0, "from_session": "2026-10-08"}]}}}
    if not legacy:
        observations.update(signals={"burst:OLD:2026-09-21:abc": {
            "ticker": "OLD", "kind": "burst", "session": "2026-09-21", "rules_version": "abc"}},
            history_max=20)
    value = {"schema_version": 2, "run": {"session": "2026-10-08", "email": email},
             "bursts": [{"ticker": "NEW", "close": 1.0, "evidence": {"id": "unchanged"},
                         "series": [{"date": "2026-10-08", "c": 1.0}], "name": "Café"}],
             "open_plans": [{"ticker": "OLD", "evidence_ref": {"id": "exact"}}],
             "observations": observations}
    return (json.dumps(value, indent=1, ensure_ascii=False) + "\n").encode()


@pytest.mark.parametrize("legacy", [False, True])
def test_complete_hydration_matches_source_without_altering_receipts_or_legacy_shape(legacy):
    raw = canonical(legacy=legacy)
    projected_raw, observation_raw = reader.derive(raw)
    assert reader.derive(raw) == (projected_raw, observation_raw)
    projected = reader.parse_reader(projected_raw)
    source = json.loads(raw)
    assert projected["canonical"] == {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    assert projected["data"]["observations"]["symbols"] == {}
    assert ("signals" in projected["data"]["observations"]) is not legacy
    assert projected["data"]["bursts"] == source["bursts"]
    assert projected["data"]["open_plans"] == source["open_plans"]
    projected["data"]["observations"] = json.loads(observation_raw)
    assert projected["data"] == source
    assert reader.validate_bundle(raw, projected_raw, observation_raw)["sha256"] == hashlib.sha256(observation_raw).hexdigest()
    assert reader.binding(raw) == {"reader_projection_version": 1,
                                   "reader_sha256": hashlib.sha256(projected_raw).hexdigest()}


def test_raw_canonical_republication_changes_reader_binding_even_with_identical_observations():
    first, second = canonical(), canonical() + b"\n"
    a, a_obs = reader.derive(first)
    b, b_obs = reader.derive(second)
    assert a_obs == b_obs and a != b
    assert reader.binding(first) != reader.binding(second)


@pytest.mark.parametrize("change", ["canonical", "reader", "observations"])
def test_equivalent_json_with_different_bytes_is_not_the_bound_bundle(change):
    raw = canonical()
    projected, observations = reader.derive(raw)
    args = [raw, projected, observations]
    args[["canonical", "reader", "observations"].index(change)] += b"\n"
    with pytest.raises(ValueError, match="differ"):
        reader.validate_bundle(*args)


@pytest.mark.parametrize("change", ["version", "hash", "path", "bytes", "extra", "bulk"])
def test_malformed_descriptor_cannot_select_another_path(change):
    envelope = reader.parse_reader(reader.derive(canonical())[0])
    if change == "version": envelope["projection_version"] = True
    if change == "hash": envelope["retained_observations"]["sha256"] = "A" * 64
    if change == "path": envelope["retained_observations"]["path"] = "../data.json"
    if change == "bytes": envelope["canonical"]["bytes"] = True
    if change == "extra": envelope["retained_observations"]["url"] = "https://example.invalid"
    if change == "bulk": envelope["data"]["observations"]["symbols"] = {"PRIVATE": {}}
    with pytest.raises(ValueError):
        reader.parse_reader(json.dumps(envelope).encode())


def test_malformed_or_overlarge_source_cannot_generate_assets(monkeypatch):
    with pytest.raises(ValueError): reader.derive(b"{broken")
    with pytest.raises(ValueError): reader.derive(canonical().replace(b"12.0", b"NaN"))
    monkeypatch.setattr(reader, "MAX_PUBLICATION_BYTES", len(canonical()) - 1)
    with pytest.raises(ValueError, match="bound"): reader.derive(canonical())


@pytest.mark.parametrize("limit", ["MAX_READER_BYTES", "MAX_OBSERVATION_BYTES"])
def test_each_derived_asset_has_its_own_absolute_bound(limit, monkeypatch):
    monkeypatch.setattr(reader, limit, 1)
    with pytest.raises(ValueError, match="bound"):
        reader.derive(canonical())


def test_projection_value_tampering_cannot_keep_a_copied_canonical_digest():
    raw = canonical()
    projected, observations = reader.derive(raw)
    envelope = json.loads(projected)
    envelope["data"]["bursts"][0]["close"] = 999.0
    with pytest.raises(ValueError, match="projection differs"):
        reader.validate_bundle(raw, json.dumps(envelope).encode(), observations)


def staged(tmp_path, raw, name="stage"):
    stage = tmp_path / name
    stage.mkdir()
    (stage / "data.json").write_bytes(raw)
    (stage / "picks.json").write_bytes(b'{"picks":"exact source bytes"}\n')
    reader.stage_assets(stage)
    return stage


@pytest.mark.parametrize("previous", [False, True])
@pytest.mark.parametrize("failure", ["sidecar", "retention.json", "reader.json", "picks.json", "data.json", None])
def test_fixed_publication_rollback_and_sidecar_installation_order(previous, failure, tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    if previous:
        old = staged(tmp_path, canonical(email="old"), "old-stage")
        reader.install_publication(old, docs, ["picks.json", "data.json"])
    old_files = {p.relative_to(docs): p.read_bytes() for p in docs.rglob("*.json")}
    stage = staged(tmp_path, canonical(email="new"))
    replace = reader.os.replace
    installs, failed = [], []

    def inject(source, target):
        target = Path(target)
        label = "sidecar" if target.parent == docs / reader.OBSERVATION_DIR and target.name != "retention.json" else target.name
        if target.parent in (docs, docs / reader.OBSERVATION_DIR):
            if label == failure and not failed:
                failed.append(label)
                raise OSError("reader publication injected failure")
            installs.append(label)
        return replace(source, target)

    # The two publications need different observation objects for sidecar controls.
    data = json.loads((stage / "data.json").read_bytes())
    data["observations"]["symbols"]["OLD"]["c"] = 13.0
    (stage / "data.json").write_bytes(json.dumps(data).encode())
    reader.stage_assets(stage)
    monkeypatch.setattr(reader.os, "replace", inject)
    if failure:
        with pytest.raises(OSError, match="injected"):
            reader.install_publication(stage, docs, ["picks.json", "data.json"])
        assert failed == [failure]
        for name in ("reader.json", "picks.json", "data.json", reader.RETENTION_FILE):
            if Path(name) in old_files: assert (docs / name).read_bytes() == old_files[Path(name)]
            else: assert not (docs / name).exists()
        for name, body in old_files.items(): assert (docs / name).read_bytes() == body
    else:
        expected = (stage / "data.json").read_bytes()
        reader.install_publication(stage, docs, ["picks.json", "data.json"])
        assert installs == ["sidecar", "retention.json", "reader.json", "picks.json", "data.json"]
        assert (docs / "data.json").read_bytes() == expected
        assert (docs / "picks.json").read_bytes() == b'{"picks":"exact source bytes"}\n'
        reader.check_assets(docs)


@pytest.mark.parametrize("bound", ["count", "bytes"])
def test_capacity_exhaustion_never_deletes_old_objects_or_changes_fixed_publication(bound, tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    reader.install_publication(staged(tmp_path, canonical(), "first"), docs, ["picks.json", "data.json"])
    old = {p.relative_to(docs): p.read_bytes() for p in docs.rglob("*.json")}
    data = json.loads(canonical(email="new"))
    data["observations"]["symbols"]["OLD"]["c"] = 99.0
    stage = staged(tmp_path, json.dumps(data).encode())
    if bound == "count": monkeypatch.setattr(reader, "MAX_SIDECARS", 1)
    else: monkeypatch.setattr(reader, "MAX_ARCHIVE_BYTES", 1)
    with pytest.raises(ValueError, match="explicit retention decision"):
        reader.install_publication(stage, docs, ["picks.json", "data.json"])
    assert {p.relative_to(docs): p.read_bytes() for p in docs.rglob("*.json")} == old


def test_corrupt_existing_immutable_object_is_refused_and_never_repaired(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    stage = staged(tmp_path, canonical())
    ref = reader.parse_reader((stage / "reader.json").read_bytes())["retained_observations"]
    target = docs / ref["path"]
    target.parent.mkdir()
    target.write_bytes(b"original corrupt bytes")
    with pytest.raises(ValueError, match="existing reader observation object differs"):
        reader.install_publication(stage, docs, ["picks.json", "data.json"])
    assert target.read_bytes() == b"original corrupt bytes"
    assert not (docs / "data.json").exists() and not (docs / "reader.json").exists()


def test_symlink_archive_cannot_redirect_retained_writes(tmp_path):
    docs, outside = tmp_path / "docs", tmp_path / "outside"
    docs.mkdir(); outside.mkdir()
    (docs / reader.OBSERVATION_DIR).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        reader.install_publication(staged(tmp_path, canonical()), docs, ["picks.json", "data.json"])
    assert not list(outside.iterdir()) and not (docs / "data.json").exists()


def test_unknown_archive_file_is_preserved_and_never_claimed_by_housekeeping(tmp_path):
    docs = tmp_path / "docs"
    archive = docs / reader.OBSERVATION_DIR
    archive.mkdir(parents=True)
    unknown = archive / "owner-kept-copy.json"
    unknown.write_bytes(b"never delete unknown files")
    reader.install_publication(staged(tmp_path, canonical()), docs, ["picks.json", "data.json"])
    assert unknown.read_bytes() == b"never delete unknown files"
    assert unknown.name not in json.loads((docs / reader.RETENTION_FILE).read_bytes())["objects"]


def test_existing_sidecar_reused_and_older_tab_object_retained(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    first = staged(tmp_path, canonical(), "first")
    reader.install_publication(first, docs, ["picks.json", "data.json"])
    objects = {p.name: p.read_bytes() for p in (docs / reader.OBSERVATION_DIR).iterdir()}
    second = staged(tmp_path, canonical(email="delivered"), "second")
    reader.install_publication(second, docs, ["data.json"])
    assert {p.name: p.read_bytes() for p in (docs / reader.OBSERVATION_DIR).iterdir()} == objects
    reader.check_assets(docs)


def dated_source(day, close):
    value = json.loads(canonical())
    value["run"]["session"] = day.isoformat()
    value["observations"]["symbols"]["OLD"]["c"] = float(close)
    return json.dumps(value).encode()


def publish_dated(tmp_path, docs, day, close):
    suffix = len(list(tmp_path.glob("day-*")))
    stage = staged(tmp_path, dated_source(day, close), f"day-{day}-{close}-{suffix}")
    ref = reader.parse_reader((stage / reader.READER_FILE).read_bytes())["retained_observations"]
    reader.install_publication(stage, docs, ["picks.json", "data.json"])
    reader.check_assets(docs)
    return ref


def test_owned_daily_transport_retains_grace_and_prunes_after_it_without_capacity_growth(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    start = date(2026, 9, 1)
    # A tight test capacity proves normal housekeeping recovers space, rather
    # than merely allowing the first few publications into a large archive.
    monkeypatch.setattr(reader, "MAX_SIDECARS", reader.RETENTION_DAYS + 2)
    refs = {}
    for offset in range(reader.RETENTION_DAYS * 2):
        day = start + timedelta(days=offset)
        refs[offset] = publish_dated(tmp_path, docs, day, offset + 1)
        index = json.loads((docs / reader.RETENTION_FILE).read_bytes())
        assert len(index["objects"]) <= reader.RETENTION_DAYS + 2
        assert (docs / refs[offset]["path"]).exists()
    # First object was superseded on day1: its grace expires after day22.
    assert not (docs / refs[0]["path"]).exists()
    for offset in range(reader.RETENTION_DAYS, reader.RETENTION_DAYS * 2):
        assert (docs / refs[offset]["path"]).exists()
    assert len(list((docs / reader.OBSERVATION_DIR).glob("*.json"))) <= reader.RETENTION_DAYS + 3


def test_current_old_object_grace_starts_at_supersession_after_publication_gap(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    old = publish_dated(tmp_path, docs, date(2026, 1, 1), 1)
    publish_dated(tmp_path, docs, date(2026, 10, 1), 2)
    assert (docs / old["path"]).exists()
    publish_dated(tmp_path, docs, date(2026, 10, 22), 3)
    assert (docs / old["path"]).exists()  # Exact21day boundary remains retained.
    publish_dated(tmp_path, docs, date(2026, 10, 23), 4)
    assert not (docs / old["path"]).exists()


def test_only_manifest_owned_expired_hashes_can_be_pruned(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    first = publish_dated(tmp_path, docs, date(2026, 1, 1), 1)
    publish_dated(tmp_path, docs, date(2026, 1, 2), 2)
    body = b'{"unindexed":"publicly retained by somebody else"}'
    unowned = docs / reader.OBSERVATION_DIR / (hashlib.sha256(body).hexdigest() + ".json")
    unowned.write_bytes(body)
    unrelated = docs / "evidence" / "keep.json"
    unrelated.parent.mkdir()
    unrelated.write_bytes(b"canonical evidence unrelated to transport")
    publish_dated(tmp_path, docs, date(2026, 2, 1), 3)
    assert not (docs / first["path"]).exists()
    assert unowned.read_bytes() == body
    assert unrelated.read_bytes() == b"canonical evidence unrelated to transport"


def test_tampered_current_pointer_cannot_acquire_ownership_of_unindexed_file(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    publish_dated(tmp_path, docs, date(2026, 1, 1), 1)
    foreign = b'{"symbols":{"UNOWNED":{"date":"2026-01-01","c":123}}}'
    sha = hashlib.sha256(foreign).hexdigest()
    path = f"{reader.OBSERVATION_DIR}/{sha}.json"
    (docs / path).write_bytes(foreign)
    envelope = json.loads((docs / reader.READER_FILE).read_bytes())
    envelope["retained_observations"] = {"sha256": sha, "bytes": len(foreign), "path": path}
    (docs / reader.READER_FILE).write_bytes(json.dumps(envelope).encode())
    old = {p.relative_to(docs): p.read_bytes() for p in docs.rglob("*.json")}
    with pytest.raises(ValueError, match="ownership was not changed"):
        publish_dated(tmp_path, docs, date(2026, 1, 2), 2)
    assert {p.relative_to(docs): p.read_bytes() for p in docs.rglob("*.json")} == old
    assert sha not in json.loads((docs / reader.RETENTION_FILE).read_bytes())["objects"]


def test_missing_current_derived_object_can_be_recreated_from_exact_canonical_source(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    first = publish_dated(tmp_path, docs, date(2026, 1, 1), 1)
    (docs / first["path"]).unlink()
    second = publish_dated(tmp_path, docs, date(2026, 1, 1), 1)
    assert first == second and (docs / first["path"]).exists()


def test_unreadable_ownership_manifest_preserves_all_files_and_refuses_new_publication(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    publish_dated(tmp_path, docs, date(2026, 1, 1), 1)
    (docs / reader.RETENTION_FILE).write_bytes(b"{unreadable")
    before = {p.relative_to(docs): p.read_bytes() for p in docs.rglob("*.json")}
    with pytest.raises(ValueError):
        publish_dated(tmp_path, docs, date(2026, 2, 1), 2)
    assert {p.relative_to(docs): p.read_bytes() for p in docs.rglob("*.json")} == before


def test_expiry_does_not_run_when_fixed_publication_rolls_back(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    first = publish_dated(tmp_path, docs, date(2026, 1, 1), 1)
    publish_dated(tmp_path, docs, date(2026, 1, 2), 2)
    old = {p.relative_to(docs): p.read_bytes() for p in docs.rglob("*.json")}
    replace = reader.os.replace
    failed = []
    def fault(source, target):
        if Path(target) == docs / "data.json" and not failed:
            failed.append(True)
            raise OSError("fixed publication failed")
        return replace(source, target)
    monkeypatch.setattr(reader.os, "replace", fault)
    with pytest.raises(OSError, match="fixed publication"):
        publish_dated(tmp_path, docs, date(2026, 2, 1), 3)
    for path, body in old.items(): assert (docs / path).read_bytes() == body
    assert (docs / first["path"]).exists()


def test_failed_expired_cleanup_remains_owned_for_retry_and_reports_verified_publication(tmp_path, monkeypatch, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    first = publish_dated(tmp_path, docs, date(2026, 1, 1), 1)
    publish_dated(tmp_path, docs, date(2026, 1, 2), 2)
    original = Path.unlink
    def fail(path, *args, **kwargs):
        if path == docs / first["path"]: raise OSError("injected cleanup failure")
        return original(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail)
        publish_dated(tmp_path, docs, date(2026, 2, 1), 3)
    assert "verified publication is intact" in capsys.readouterr().out
    index = json.loads((docs / reader.RETENTION_FILE).read_bytes())
    assert first["sha256"] in index["objects"] and (docs / first["path"]).exists()
    publish_dated(tmp_path, docs, date(2026, 2, 2), 4)
    assert not (docs / first["path"]).exists()


def test_cleanup_manifest_failure_does_not_accumulate_already_deleted_ownership(tmp_path, monkeypatch, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    monkeypatch.setattr(reader, "MAX_SIDECARS", 3)
    first = publish_dated(tmp_path, docs, date(2026, 1, 1), 1)
    second = publish_dated(tmp_path, docs, date(2026, 1, 2), 2)
    publish_dated(tmp_path, docs, date(2026, 1, 3), 3)
    replace = reader.os.replace
    attempts = []
    def fail_cleanup(source, target):
        if Path(target) == docs / reader.RETENTION_FILE:
            attempts.append(True)
            if len(attempts) == 2: raise OSError("cleanup manifest rename failed")
        return replace(source, target)
    with monkeypatch.context() as patch:
        patch.setattr(reader.os, "replace", fail_cleanup)
        publish_dated(tmp_path, docs, date(2026, 2, 1), 4)
    assert "verified publication is intact" in capsys.readouterr().out
    assert not (docs / first["path"]).exists() and not (docs / second["path"]).exists()
    old_index = json.loads((docs / reader.RETENTION_FILE).read_bytes())
    assert len(old_index["objects"]) == 4  # Published metadata still owns absent expired files.
    stage = staged(tmp_path, dated_source(date(2026, 2, 2), 5), "recovery-stage")
    reader_raw = (stage / reader.READER_FILE).read_bytes()
    ref = reader.parse_reader(reader_raw)["retained_observations"]
    index, expired, additions = reader._retention(stage, docs, ref, (stage / "data.json").read_bytes())
    assert first["sha256"] not in index["objects"] and second["sha256"] not in index["objects"]
    assert len(index["objects"]) == 3
    reader.install_publication(stage, docs, ["picks.json", "data.json"])
    reader.check_assets(docs)


@pytest.mark.parametrize("send_fails", [False, True])
def test_pipeline_final_and_email_failure_restamps_bind_actual_final_canonical_bytes(
        market, claude, fake_resend, tmp_path, monkeypatch, send_fails):
    from src import report
    installed = []
    install = reader.install_publication

    def track(stage, docs, names):
        install(stage, docs, names)
        raw = (Path(docs) / "data.json").read_bytes()
        envelope = reader.parse_reader((Path(docs) / "reader.json").read_bytes())
        assert envelope["canonical"]["sha256"] == hashlib.sha256(raw).hexdigest()
        installed.append((raw, envelope))

    monkeypatch.setattr(reader, "install_publication", track)
    if send_fails:
        def fail(data): raise RuntimeError("injected delivery outage")
        monkeypatch.setattr(report, "send_digest", fail)
    rep, data, docs = evening(tmp_path, market)
    assert rep.published and len(installed) == 2
    assert installed[0][0] != installed[1][0]
    assert installed[1][0] == (docs / "data.json").read_bytes()
    assert data["run"]["email"] == ("failed" if send_fails else "delivered")
    reader.check_assets(docs)
