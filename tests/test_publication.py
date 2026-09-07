"""The website refresh is a separate boundary from a successful commit-back."""
from http.client import IncompleteRead
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
import yaml

from tools import publish_dashboard as publication


ROOT = Path(__file__).resolve().parent.parent
FILES = {"index.html": b"<html>actual dashboard</html>",
         "data.json": b'{"run":{"date":"2026-09-08"}}',
         "ledger.json": b'{"runs":[{"date":"2026-09-08"}]}'}


@pytest.fixture
def delivery(monkeypatch, tmp_path):
    (tmp_path / "docs").mkdir()
    for name, content in FILES.items():
        (tmp_path / "docs" / name).write_bytes(content)
    calls = []
    site = {"build_type": "legacy", "source": {"branch": "main", "path": "/docs"},
            "html_url": "https://example.github.io/SpicyStock/"}

    def api(repository, endpoint, method="GET"):
        calls.append((repository, endpoint, method))
        return site if endpoint == "pages" else {"status": "queued"}

    def public(url, timeout):
        name = urlsplit(url).path.rsplit("/", 1)[-1]
        assert name in FILES
        assert 0 < timeout <= 20
        query = parse_qs(urlsplit(url).query)
        assert "publication" in query and "attempt" in query
        return FILES[name]

    clock = [0.0]
    monkeypatch.setattr(publication, "github_api", api)
    monkeypatch.setattr(publication, "public_bytes", public)
    monkeypatch.setattr(publication.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(publication.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    return SimpleNamespace(root=tmp_path, site=site, calls=calls, clock=clock, public=public)


def test_publication_explicitly_requests_pages_then_verifies_committed_files(delivery, capsys):
    publication.publish("owner/repo", delivery.root)
    assert delivery.calls == [("owner/repo", "pages", "GET"),
                              ("owner/repo", "pages/builds", "POST")]
    assert "match committed main" in capsys.readouterr().out


@pytest.mark.parametrize("stale_name", FILES)
def test_an_old_public_file_never_passes_as_a_successful_refresh(delivery, monkeypatch, stale_name):
    def public(url, timeout):
        return b"old deployed file" if f"/{stale_name}?" in url else delivery.public(url, timeout)

    monkeypatch.setattr(publication, "public_bytes", public)
    with pytest.raises(RuntimeError, match=stale_name):
        publication.publish("owner/repo", delivery.root)
    assert delivery.clock[0] == 480


def test_partial_deployment_retries_until_all_three_files_are_current(delivery, monkeypatch):
    attempts = []

    def public(url, timeout):
        name = urlsplit(url).path.rsplit("/", 1)[-1]
        attempts.append(name)
        if name == "data.json" and delivery.clock[0] < 20:
            return b"Friday's snapshot while Tuesday's HTML is already live"
        return delivery.public(url, timeout)

    monkeypatch.setattr(publication, "public_bytes", public)
    publication.publish("owner/repo", delivery.root)
    assert delivery.clock[0] == 20
    assert all(attempts.count(name) == 3 for name in FILES)


@pytest.mark.parametrize("interruption", [OSError("temporary transport failure"),
                                         IncompleteRead(b"partial public response", 100)])
def test_public_network_failure_is_retried_but_never_called_verified(delivery, monkeypatch, capsys,
                                                                  interruption):
    def unreachable(*args):
        raise interruption

    monkeypatch.setattr(publication, "public_bytes", unreachable)
    with pytest.raises(RuntimeError, match="deadline"):
        publication.publish("owner/repo", delivery.root)
    assert "Verified:" not in capsys.readouterr().out


def test_a_truncated_response_retries_and_can_recover(delivery, monkeypatch):
    def interrupted(url, timeout):
        if delivery.clock[0] == 0:
            raise IncompleteRead(b"partial public response", 100)
        return delivery.public(url, timeout)

    monkeypatch.setattr(publication, "public_bytes", interrupted)
    publication.publish("owner/repo", delivery.root)
    assert delivery.clock[0] == 10


@pytest.mark.parametrize("field,value", [
    ("build_type", "workflow"),
    ("source", {"branch": "preview", "path": "/docs"}),
    ("source", {"branch": "main", "path": "/"}),
    ("html_url", "http://example.github.io/SpicyStock/"),
    ("html_url", "https://example.github.io/SpicyStock/?redirect=elsewhere"),
])
def test_wrong_pages_settings_fail_without_changing_them(delivery, field, value):
    delivery.site[field] = value
    with pytest.raises(RuntimeError, match="Pages"):
        publication.publish("owner/repo", delivery.root)
    assert delivery.calls == [("owner/repo", "pages", "GET")]


def test_publication_fails_if_the_api_does_not_acknowledge_the_build(delivery, monkeypatch):
    monkeypatch.setattr(publication, "github_api", lambda repository, endpoint, method="GET":
                        delivery.site if endpoint == "pages" else {"status": "errored"})
    with pytest.raises(RuntimeError, match="acknowledge"):
        publication.publish("owner/repo", delivery.root)


def test_gh_failure_stops_publication_and_does_not_print_the_response(monkeypatch):
    calls = []

    def refused(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=1, stdout="", stderr="private API error detail")

    monkeypatch.setattr(publication.subprocess, "run", refused)
    with pytest.raises(RuntimeError, match="GitHub POST pages/builds failed") as failure:
        publication.github_api("owner/repo", "pages/builds", "POST")
    assert "private" not in str(failure.value)
    assert calls[0][0] == ["gh", "api", "--method", "POST", "repos/owner/repo/pages/builds",
                           "-H", "Accept: application/vnd.github+json"]
    assert calls[0][1]["timeout"] == 30


def test_public_fetch_does_not_forward_the_job_token(monkeypatch):
    requests = []

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b"public content"

    monkeypatch.setenv("GH_TOKEN", "test-only-token")
    monkeypatch.setattr(publication, "urlopen", lambda request, timeout:
                        requests.append((request, timeout)) or Reply())
    assert publication.public_bytes("https://custom-domain.example/data.json", 10) == b"public content"
    request, timeout = requests[0]
    assert request.full_url == "https://custom-domain.example/data.json"
    assert timeout == 10 and not request.has_header("Authorization")
    assert request.header_items() == [("Cache-control", "no-cache")]


def test_publication_is_triggered_after_evening_and_deploys_only_committed_main():
    workflow = yaml.safe_load((ROOT / ".github/workflows/publish-dashboard.yml").read_text())
    trigger = workflow.get("on", workflow.get(True))
    evening = yaml.safe_load((ROOT / ".github/workflows/evening.yml").read_text())
    assert trigger["workflow_run"] == {"workflows": [evening["name"]],
                                       "types": ["completed"], "branches": ["main"]}
    assert trigger["push"]["branches"] == ["main"]
    assert {"docs/**", "tools/publish_dashboard.py", ".github/workflows/publish-dashboard.yml"} \
        <= set(trigger["push"]["paths"])
    assert workflow["permissions"] == {"contents": "read", "pages": "write"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    job = workflow["jobs"]["publish"]
    condition = " ".join(job["if"].split())
    assert "github.ref == 'refs/heads/main'" in condition
    assert "conclusion != 'cancelled'" in condition
    assert "head_repository.full_name == github.repository" in condition
    # Success-only would lose precisely the exit 2/3 records already persisted.
    assert "conclusion == 'success'" not in condition
    checkout = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout"))
    assert checkout["with"] == {"ref": "main", "persist-credentials": False}
    assert not any("download-artifact" in step.get("uses", "") for step in job["steps"])
    run = next(step for step in job["steps"] if "run" in step)
    assert run["run"] == "python tools/publish_dashboard.py"
    assert run["env"] == {"GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}"}
