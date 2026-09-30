"""Small deterministic profiles; no full-shape benchmark in ordinary pytest."""
from copy import deepcopy
import json
import inspect
from types import SimpleNamespace

import pytest

from tools import historical_runtime_profile as profiling
from tools import historical_projection_benchmark as benchmark


def test_nested_stage_wall_cpu_and_sampled_peaks_are_not_double_counted():
    clock = SimpleNamespace(wall=0.0, cpu=0.0, rss=100)
    profile = profiling.RuntimeProfile(wall=lambda: clock.wall, cpu=lambda: clock.cpu, rss=lambda: clock.rss)
    with profile.scope("normalization"):
        clock.wall, clock.cpu = 1, 0.5
        with profile.scope("parsing"):
            clock.wall, clock.cpu, clock.rss = 4, 2, 300
            profile.observe(1234)
        clock.wall, clock.cpu = 6, 3
    report = profile.report()
    assert report["active_stages"] == []
    outer, inner = report["stages"]["normalization"], report["stages"]["parsing"]
    assert (outer["wall_inclusive_seconds"], outer["wall_exclusive_seconds"]) == (6, 3)
    assert (outer["cpu_inclusive_seconds"], outer["cpu_exclusive_seconds"]) == (3, 1.5)
    assert inner["wall_inclusive_seconds"] == inner["wall_exclusive_seconds"] == 3
    assert outer["sampled_peak_rss_bytes"] == inner["sampled_peak_rss_bytes"] == 300
    assert outer["sampled_peak_scratch_bytes"] == 1234


def test_failed_stage_is_measured_and_exception_is_preserved():
    profile = profiling.RuntimeProfile(rss=lambda: None)
    failure = ValueError("synthetic failure")
    with pytest.raises(ValueError) as caught:
        with profile.scope("parsing"):
            raise failure
    assert caught.value is failure
    row = profile.report()["stages"]["parsing"]
    assert row["failures"] == row["calls"] == row["completed"] == 1
    assert row["sampled_peak_rss_bytes"] is None


def test_linux_completed_child_high_water_is_not_labelled_age_only():
    result = benchmark.memory_summary({"process_peak_rss_bytes": 1000}, {"completed_children_peak_rss_bytes": 200})
    assert result["python_plus_completed_children_peak_rss_conservative_sum_bytes"] == 1200
    assert result["python_plus_age_peak_rss_conservative_sum_bytes"] is None
    assert "not simultaneous or age-only" in result["scope"]


def test_profile_binds_complete_compatibility_sources_manifest_and_prior_scientific_inventory():
    contract = json.loads((benchmark.ROOT / "tools/historical-delivery-compatibility.json").read_bytes())
    paths = set(benchmark.SOURCE_FILES)
    assert set(contract["required_source_paths"]) <= paths
    assert benchmark.MANIFEST.relative_to(benchmark.ROOT).as_posix() in paths
    assert {"docs/input-truthfulness/2026-09-30-projection-compaction-evidence/benchmark-" + case + suffix
            for case in benchmark.CASES for suffix in (".json", "-members.json")} <= paths
    assert list(benchmark.SOURCE_FILES) == sorted(paths)


def test_actual_small_instrumentation_preserves_frames_projection_and_restores_imports():
    from tools import historical_reconcile as reconciliation
    from tools import historical_normalization as normalization
    from tests.test_historical_normalization import page, query, row
    from tests.test_historical_projection import assert_frames_equal
    pages = [page([row("2026-09-24"), row()])]
    keywords = dict(query=query(), terminal=True, target_session="2026-09-25")
    original_normalize, original_projection, original_json = reconciliation.normalize_pages, reconciliation.frames_for_replay, normalization.json
    normal = original_normalize(pages, **keywords)
    before_frames, before = original_projection(normal, projection_contract=normalization.COMPACT_PROJECTION)
    profile = profiling.RuntimeProfile()
    with profiling.instrument(profile):
        measured = reconciliation.normalize_pages(pages, **keywords)
        frames, projection = reconciliation.frames_for_replay(measured, projection_contract=normalization.COMPACT_PROJECTION)
        raw = reconciliation.encode(measured)
    assert measured == normal and projection == before and json.loads(raw) == normal
    assert_frames_equal(frames, before_frames)
    assert reconciliation.normalize_pages is original_normalize and reconciliation.frames_for_replay is original_projection
    assert normalization.json is original_json
    assert set(profile.report()["stages"]) == {"normalization", "parsing", "projection", "projection_hashing", "serialization"}
    assert profile.report()["stages"]["projection_hashing"]["calls"] == 2


def test_instrumentation_restores_imports_on_interruption():
    from tools import historical_reconcile as reconciliation
    original = reconciliation.frames_for_replay
    with pytest.raises(profiling.RuntimeDeadline):
        with profiling.instrument(profiling.RuntimeProfile()):
            raise profiling.RuntimeDeadline("synthetic_deadline")
    assert reconciliation.frames_for_replay is original


def test_deadline_post_return_check_does_not_silently_pass_on_unsupported_platform(monkeypatch):
    clock = iter((0, 2))
    monkeypatch.setattr(profiling, "signal", SimpleNamespace())
    monkeypatch.setattr(profiling.time, "monotonic", lambda: next(clock))
    with pytest.raises(profiling.RuntimeDeadline, match="shared_offline_deadline_exceeded"):
        with profiling.deadline("shared_offline", 1):
            pass


def test_fired_deadline_survives_native_exception_wrapping_without_relabelling_other_errors(monkeypatch):
    prior = lambda *_: None
    state = {"handler": prior}
    fake = SimpleNamespace(SIGALRM=14, ITIMER_REAL=0, getsignal=lambda _: prior,
        getitimer=lambda _: (0, 0), signal=lambda _, handler: state.update(handler=handler),
        setitimer=lambda *args: None)
    monkeypatch.setattr(profiling, "signal", fake)
    monkeypatch.setattr(profiling.time, "monotonic", lambda: 0)
    with pytest.raises(profiling.RuntimeDeadline, match="package_deadline_exceeded") as caught:
        with profiling.deadline("package", 600):
            try:
                state["handler"]()
            except profiling.RuntimeDeadline as error:
                raise RuntimeError("native wrapper converted the callback failure") from error
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert state["handler"] is prior
    with pytest.raises(RuntimeError, match="unrelated codec failure"):
        with profiling.deadline("package", 600):
            raise RuntimeError("unrelated codec failure")
    assert state["handler"] is prior


@pytest.mark.parametrize("boundary", ["normalization", "production"])
def test_deadline_crosses_actual_malformed_data_handlers(monkeypatch, boundary):
    stop = profiling.RuntimeDeadline("shared_offline_initial_deadline_exceeded")
    calls = []
    def expired(*_, **__):
        calls.append(True)
        raise stop
    if boundary == "normalization":
        from tools import historical_normalization as normalization
        from tests.test_historical_normalization import page, query, row
        monkeypatch.setattr(normalization, "_decimal", expired)
        invoke = lambda: normalization.normalize_pages([page([row()])], query=query(), terminal=True,
                                                       target_session="2026-09-25")
    else:
        from src import breadth
        from tests.test_historical_breadth_reference import frame, run
        monkeypatch.setattr(breadth, "daily_counts", expired)
        invoke = lambda: run({"A": frame()})
    with pytest.raises(profiling.RuntimeDeadline) as caught:
        invoke()
    assert caught.value is stop and calls == [True]


def test_complete_offline_passes_and_reserved_acquisition_share_original_envelope():
    phases = {"reconcile_2026-09-24": 700, "reconcile_2026-09-25": 800,
              "reproduce_2026-09-24": 600, "reproduce_2026-09-25": 700, "package": 500}
    result = benchmark.timing_acceptance(phases, 100, 840.014, representative=True, required_passes_completed=True)
    assert result["status"] == "PASS"
    assert result["prospective_reserved_total_seconds"] == 4200
    assert result["remaining_total_seconds_before_overhead_reserve"] == 600
    assert result["remaining_total_seconds_after_overhead_reserve"] == 300
    assert result["delivery_overhead_reserve_seconds"] == 300
    assert result["delivery_overhead_reserve_basis"].startswith("ASSUMPTION:")
    assert result["initial_shared_offline_seconds"] == 1500
    assert result["recovered_shared_offline_seconds"] == 1300
    assert not result["http_retry_and_provider_delay_measured"]
    assert result["original_limits_seconds"] == {"acquisition_guard": 1500, "acquisition_step": 1800,
        "offline_step": 1800, "package_step": 600, "total_job": 4500}


@pytest.mark.parametrize("change", [
    {"reconcile_2026-09-24": 1000, "reconcile_2026-09-25": 801},
    {"reproduce_2026-09-24": 1000, "reproduce_2026-09-25": 801},
    {"package": 601},
])
def test_shared_deadline_cannot_be_evaded_with_individually_short_dates(change):
    phases = {"reconcile_2026-09-24": 600, "reconcile_2026-09-25": 600,
              "reproduce_2026-09-24": 600, "reproduce_2026-09-25": 600, "package": 500}
    phases.update(change)
    assert benchmark.timing_acceptance(phases, 100, 840.014, representative=True, required_passes_completed=True)["status"] == "FAIL"


def test_total_envelope_and_missing_reproduction_fail_independently():
    phases = {"reconcile_2026-09-24": 800, "reconcile_2026-09-25": 900,
              "reproduce_2026-09-24": 500, "reproduce_2026-09-25": 500, "package": 600}
    assert benchmark.timing_acceptance(phases, 401, 840.014, representative=True, required_passes_completed=True)["status"] == "FAIL"
    del phases["reproduce_2026-09-24"], phases["reproduce_2026-09-25"]
    assert benchmark.timing_acceptance(phases, 0, 840.014, representative=True, required_passes_completed=True)["status"] == "FAIL"


@pytest.mark.parametrize("setup,expected", [(300, "FAIL"), (1, "FAIL"), (0, "PASS")])
def test_delivery_overhead_reserve_refuses_zero_or_insufficient_headroom(setup, expected):
    phases = {"reconcile_2026-09-24": 900, "reconcile_2026-09-25": 900,
              "reproduce_2026-09-24": 500, "reproduce_2026-09-25": 500, "package": 600}
    result = benchmark.timing_acceptance(phases, setup, 840.014, representative=True, required_passes_completed=True)
    assert result["status"] == expected
    assert result["remaining_total_seconds_before_overhead_reserve"] == 300 - setup
    assert result["remaining_total_seconds_after_overhead_reserve"] == -setup


def test_pr96_inventory_verifier_rejects_changed_raw_or_scientific_bytes():
    expected = json.loads((benchmark.ROOT / "docs/input-truthfulness/2026-09-30-projection-compaction-evidence/benchmark-central-members.json").read_bytes())
    result = benchmark.verify_original_outputs("central", expected)
    assert result["status"] == "PASS" and len(result["reconciliation"]) == 2
    for name in (next(n for n in expected if n.startswith("pages/")), "reconciliation-2026-09-24.json"):
        changed = deepcopy(expected)
        changed[name]["sha256"] = "0" * 64
        with pytest.raises(ValueError, match="scientific_member_bytes_changed"):
            benchmark.verify_original_outputs("central", changed)


def test_pr96_inventory_verifier_rejects_omitted_member_not_platform_sqlite():
    expected = json.loads((benchmark.ROOT / "docs/input-truthfulness/2026-09-30-projection-compaction-evidence/benchmark-central-members.json").read_bytes())
    changed = deepcopy(expected)
    changed["ledger.sqlite3"]["sha256"] = "0" * 64
    assert benchmark.verify_original_outputs("central", changed)["status"] == "PASS"
    del changed["reconciliation-2026-09-25.json"]
    with pytest.raises(ValueError, match="scientific_member_set_changed"):
        benchmark.verify_original_outputs("central", changed)


def test_removed_overhead_guard_fails_its_controls_and_preserves_unrelated_identity_check(monkeypatch):
    source = inspect.getsource(benchmark.timing_acceptance)
    old, replacement = "prospective <= 4500", "measured_and_acquisition <= 4500"
    assert source.count(old) == 1
    namespace = dict(vars(benchmark))
    exec(compile(source.replace(old, replacement), "<removed-overhead-reserve>", "exec"), namespace)
    with monkeypatch.context() as changed:
        changed.setattr(benchmark, "timing_acceptance", namespace["timing_acceptance"])
        for setup in (300, 1):
            with pytest.raises(AssertionError):
                test_delivery_overhead_reserve_refuses_zero_or_insufficient_headroom(setup, "FAIL")
        test_delivery_overhead_reserve_refuses_zero_or_insufficient_headroom(0, "PASS")
        test_pr96_inventory_verifier_rejects_changed_raw_or_scientific_bytes()
    for setup, status in ((300, "FAIL"), (1, "FAIL"), (0, "PASS")):
        test_delivery_overhead_reserve_refuses_zero_or_insufficient_headroom(setup, status)


def test_restored_valueerror_deadline_fails_actual_handlers_and_preserves_identity_check(monkeypatch):
    class RestoredDeadline(ValueError):
        pass
    with monkeypatch.context() as changed:
        changed.setattr(profiling, "RuntimeDeadline", RestoredDeadline)
        for boundary in ("normalization", "production"):
            with changed.context() as isolated:
                with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
                    test_deadline_crosses_actual_malformed_data_handlers(isolated, boundary)
        test_pr96_inventory_verifier_rejects_changed_raw_or_scientific_bytes()
    for boundary in ("normalization", "production"):
        with monkeypatch.context() as isolated:
            test_deadline_crosses_actual_malformed_data_handlers(isolated, boundary)
