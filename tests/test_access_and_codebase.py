"""Sign-in, saved keys, model settings, Ollama, and the secure repository pipeline."""

from __future__ import annotations

import io
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from apps.codebase.models import RepoBinding, RepoStatus
from apps.codebase.services import analyze_binding
from apps.journeys.models import Journey
from apps.runs.credentials import decrypt_saved_key, open_api_key
from apps.runs.models import Run, SavedCredential
from engine.code_index import build_index
from engine.code_safety import code_safety
from engine.contracts import ActionKind, PlannerObservationV1
from engine.ollama import OllamaActionClient
from engine.planner import OllamaPlanner, OllamaUnavailableError, planner_from_config
from engine.provider_models import ModelListError, list_models
from engine.repo_clone import RepoCloneError, clone_snapshot, validate_branch, validate_repo_url
from engine.secret_scan import is_blocked_path, redact

KEY = "gsk_saved_key_value_1234"
ALLOWED = ("github.com", "gitlab.com", "bitbucket.org")


# Sign-in ------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name", ["runs:list", "runs:rules", "runs:model_settings", "codebase:page"]
)
def test_every_page_requires_sign_in(anonymous_client, name) -> None:
    response = anonymous_client.get(reverse(name))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


@pytest.mark.django_db
def test_sign_in_page_is_public_and_works(anonymous_client, user) -> None:
    assert anonymous_client.get(reverse("login")).status_code == 200
    response = anonymous_client.post(
        reverse("login"), {"username": "tester", "password": "correct horse battery"}
    )
    assert response.status_code == 302
    assert anonymous_client.get(reverse("runs:list")).status_code == 200


# Saved keys and model settings ------------------------------------------------------


@pytest.mark.django_db
def test_remembered_key_is_encrypted_and_never_shown(client, user) -> None:
    client.post(
        reverse("runs:save_model_settings"),
        {"provider": "groq", "api_key": KEY, "model": "openai/gpt-oss-120b", "remember": "on"},
    )
    saved = SavedCredential.objects.get(owner=user, provider="groq")
    assert KEY not in saved.encrypted_key
    assert decrypt_saved_key(saved.encrypted_key) == KEY
    assert saved.key_hint == "••••1234"
    assert saved.is_preferred
    page = client.get(reverse("runs:model_settings") + "?provider=groq").content.decode()
    assert KEY not in page
    assert "Saved key ••••1234" in page


@pytest.mark.django_db
def test_key_is_not_stored_unless_remember_is_ticked(client, user) -> None:
    client.post(reverse("runs:save_model_settings"), {"provider": "groq", "api_key": KEY})
    assert SavedCredential.objects.get(owner=user, provider="groq").encrypted_key == ""


@pytest.mark.django_db
def test_forget_key_deletes_it(client, user) -> None:
    client.post(
        reverse("runs:save_model_settings"), {"provider": "groq", "api_key": KEY, "remember": "on"}
    )
    client.post(reverse("runs:forget_key"), {"provider": "groq"})
    saved = SavedCredential.objects.get(owner=user, provider="groq")
    assert saved.encrypted_key == "" and saved.key_hint == ""


def _journey() -> Journey:
    return Journey.objects.create(
        name="Saved key journey",
        goal="Complete a configured keyboard-only fixture journey.",
        start_url="http://127.0.0.1:8001/accessible/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={
            "planner": {"kind": "gemini.v1", "fallback": {"kind": "fixture_plan.v1"}}
        },
    )


@pytest.mark.django_db
@override_settings(GROQ_API_KEY="", GROQ_MODEL="")
def test_run_uses_the_saved_key_and_default_model(client, user) -> None:
    client.post(
        reverse("runs:save_model_settings"),
        {"provider": "groq", "api_key": KEY, "model": "openai/gpt-oss-120b", "remember": "on"},
    )
    journey = _journey()
    with patch("apps.runs.views.execute_run.delay") as delay:
        delay.return_value.id = "task"
        client.post(reverse("runs:start", args=[journey.id]), {"planner_provider": "groq"})
    run = Run.objects.get()
    assert run.planner_model == "openai/gpt-oss-120b"
    assert run.planner_metadata["credential_source"] == "saved"
    assert open_api_key(delay.call_args.kwargs["credential_token"]) == KEY


@pytest.mark.django_db
@override_settings(GROQ_API_KEY="", GROQ_MODEL="m")
def test_another_persons_saved_key_is_never_used(client, user) -> None:
    other = get_user_model().objects.create_user("other", password="x")
    other_client = Client()
    other_client.force_login(other)
    other_client.post(
        reverse("runs:save_model_settings"), {"provider": "groq", "api_key": KEY, "remember": "on"}
    )
    journey = _journey()
    with patch("apps.runs.views.execute_run.delay") as delay:
        client.post(
            reverse("runs:start", args=[journey.id]), {"planner_provider": "groq"}, follow=True
        )
    delay.assert_not_called()
    assert Run.objects.count() == 0


@pytest.mark.django_db
def test_list_models_endpoint_prefers_the_typed_key_and_hides_it_in_errors(client) -> None:
    with patch("apps.runs.model_settings.list_models", return_value=["a", "b"]) as listing:
        response = client.post(
            reverse("runs:list_models"), {"provider": "groq", "api_key": "typed-key-9876"}
        )
    assert json.loads(response.content) == {"models": ["a", "b"]}
    assert listing.call_args.kwargs["api_key"] == "typed-key-9876"
    with patch(
        "apps.runs.model_settings.list_models",
        side_effect=ModelListError("The provider rejected the API key."),
    ):
        response = client.post(
            reverse("runs:list_models"), {"provider": "groq", "api_key": "typed-key-9876"}
        )
    assert response.status_code == 502
    assert "typed-key-9876" not in response.content.decode()


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None


def test_model_lists_send_keys_only_in_headers() -> None:
    seen = []

    def opener(request, timeout):
        seen.append(request)
        if "groq" in request.full_url:
            return _Response(json.dumps({"data": [{"id": "openai/gpt-oss-120b"}]}).encode())
        if "googleapis" in request.full_url:
            return _Response(
                json.dumps(
                    {
                        "models": [
                            {
                                "name": "models/gemini-2.5-flash",
                                "supportedGenerationMethods": ["generateContent"],
                            },
                            {
                                "name": "models/embedding",
                                "supportedGenerationMethods": ["embedContent"],
                            },
                        ]
                    }
                ).encode()
            )
        return _Response(json.dumps({"models": [{"name": "llama3.1:8b"}]}).encode())

    assert list_models("groq", api_key="k1", opener=opener) == ["openai/gpt-oss-120b"]
    assert list_models("gemini", api_key="k2", opener=opener) == ["models/gemini-2.5-flash"]
    assert list_models("ollama", ollama_base_url="http://localhost:11434", opener=opener) == [
        "llama3.1:8b"
    ]
    assert all("k1" not in request.full_url and "k2" not in request.full_url for request in seen)
    assert seen[1].get_header("X-goog-api-key") == "k2"

    def rejecting(request, timeout):
        raise HTTPError(request.full_url, 401, "no", {}, io.BytesIO(b"bad key k1"))

    with pytest.raises(ModelListError, match="rejected the API key"):
        list_models("groq", api_key="k1", opener=rejecting)


def test_code_safety_blocks_gemini_free_and_openrouter_free() -> None:
    assert code_safety("ollama").safe
    assert code_safety("groq").safe
    assert not code_safety("gemini").safe
    assert not code_safety("openrouter", "openrouter/free").safe
    assert code_safety("openrouter", "x", allowed=("openrouter",)).safe


# Ollama -------------------------------------------------------------------------


def _observation() -> PlannerObservationV1:
    return PlannerObservationV1(goal="Open the page", url="https://example.org/", remaining_steps=5)


def test_ollama_client_returns_a_structured_action() -> None:
    def opener(request, timeout):
        body = json.loads(request.data)
        assert body["format"]["properties"]["action"]["enum"]
        assert request.full_url == "http://localhost:11434/api/chat"
        content = json.dumps(
            {"action": "tab", "value": None, "target_hint": "Search", "purpose": "p"}
        )
        return _Response(
            json.dumps({"model": "llama3.1:8b", "message": {"content": content}}).encode()
        )

    client = OllamaActionClient(
        base_url="http://localhost:11434/", timeout_seconds=5, opener=opener
    )
    planner = planner_from_config(
        {"planner": {"kind": "ollama.v1", "allow_no_fallback": True}},
        ollama_client=client,
        ollama_model="llama3.1:8b",
    )
    assert isinstance(planner.primary, OllamaPlanner)
    action = planner.propose_next_action(_observation())
    assert action.action == ActionKind.TAB
    assert planner.runtime_metadata()["provider"] == "ollama"


def test_ollama_errors_are_labelled_as_ollama() -> None:
    def missing_model(request, timeout):
        raise HTTPError(
            request.full_url, 404, "missing", {}, io.BytesIO(b'{"error":"model not found"}')
        )

    def offline(request, timeout):
        raise URLError(ConnectionRefusedError())

    for opener, code in (
        (missing_model, "OLLAMA_MODEL_NOT_FOUND"),
        (offline, "OLLAMA_NOT_REACHABLE"),
    ):
        client = OllamaActionClient(
            base_url="http://localhost:11434", timeout_seconds=5, opener=opener
        )
        with pytest.raises(OllamaUnavailableError) as raised:
            client.generate_action(model="m", observation=_observation())
        assert raised.value.code == code


@pytest.mark.django_db
@override_settings(OLLAMA_BASE_URL="")
def test_ollama_run_is_refused_when_ollama_is_not_configured(client) -> None:
    journey = _journey()
    response = client.post(
        reverse("runs:start", args=[journey.id]),
        {"planner_provider": "ollama", "planner_model": "llama3.1:8b"},
        follow=True,
    )
    assert "Ollama is not configured" in response.content.decode()
    assert Run.objects.count() == 0


# Repository addresses ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/owner/repo",
        "https://evil.example/owner/repo",
        "https://token@github.com/owner/repo",
        "https://github.com/owner/repo?x=1",
        "https://github.com:8443/owner/repo",
        "https://github.com/owner",
        "https://github.com/owner/repo/../../etc",
        "file:///etc",
        "ssh://git@github.com/owner/repo",
    ],
)
def test_unsafe_repository_addresses_are_refused(url) -> None:
    with pytest.raises(RepoCloneError):
        validate_repo_url(url, ALLOWED)


def test_safe_repository_address_is_normalised() -> None:
    assert validate_repo_url("https://GitHub.com/MICKEY0107/AccessPath-AI/", ALLOWED) == (
        "https://github.com/MICKEY0107/AccessPath-AI.git"
    )


@pytest.mark.parametrize("branch", ["--upload-pack=x", "a..b", "feature//x", "x.lock", "a b"])
def test_unsafe_branch_names_are_refused(branch) -> None:
    with pytest.raises(RepoCloneError):
        validate_branch(branch)


# Cloning and indexing ------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "origin"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "App.jsx").write_text(
        "export default function App() {\n"
        '  return <div className="pay" onClick={pay}>Pay now</div>;\n'
        "}\n"
        "export function Toolbar() { return <App />; }\n",
        encoding="utf-8",
    )
    (repo / "src" / "styles.css").write_text(".btn:focus { outline: none; }\n", encoding="utf-8")
    (repo / "src" / "config.js").write_text(
        'const api_key = "sk-live-abcdefghijklmnopqrstuv";\n', encoding="utf-8"
    )
    (repo / ".env").write_text("SECRET=hunter2\n", encoding="utf-8")
    (repo / "leak").symlink_to("/etc/passwd")
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("add", "-A", cwd=repo)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init", cwd=repo)
    return repo


def test_clone_keeps_plain_files_only_and_never_follows_symlinks(sample_repo, tmp_path) -> None:
    snapshot = clone_snapshot(
        f"file://{sample_repo}", tmp_path / "copy" / "src", allow_file_urls=True
    )
    assert len(snapshot.commit_sha) == 40
    assert not (snapshot.path / ".git").exists()
    leak = snapshot.path / "leak"
    assert not leak.is_symlink()
    assert "root:" not in (leak.read_text() if leak.exists() else "")
    assert (snapshot.path / "src" / "App.jsx").is_file()


def test_clone_size_limit_removes_the_copy(sample_repo, tmp_path) -> None:
    destination = tmp_path / "copy" / "src"
    with pytest.raises(RepoCloneError, match="too large"):
        clone_snapshot(f"file://{sample_repo}", destination, allow_file_urls=True, max_files=2)
    assert not destination.exists()


def test_clone_errors_never_contain_the_token(tmp_path) -> None:
    token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
    with pytest.raises(RepoCloneError) as raised:
        clone_snapshot(
            f"file://{tmp_path}/missing", tmp_path / "copy", token=token, allow_file_urls=True
        )
    assert token not in str(raised.value)


def test_index_skips_secrets_and_finds_patterns_and_components(sample_repo) -> None:
    index = build_index(sample_repo)
    paths = {item["path"] for item in index.files}
    assert ".env" not in paths and "leak" not in paths
    kinds = {item["kind"] for item in index.patterns}
    assert {"click_handler_on_non_control", "outline_removed_on_focus"} <= kinds
    assert "App" in index.components and index.components["App"]["used_in"]


def test_secret_scan_redacts_keys_and_blocks_key_files() -> None:
    text, count = redact(
        'const api_key = "sk-live-abcdefghijklmnopqrstuv"; ghp_ABCDEFGHIJKLMNOPQRSTUV123'
    )
    assert count >= 2 and "sk-live" not in text and "ghp_" not in text
    assert is_blocked_path(".env.production")
    assert is_blocked_path("certs/server.key")
    assert is_blocked_path("node_modules/x/index.js")
    assert not is_blocked_path("src/components/PasswordField.tsx")


@pytest.mark.django_db
def test_analyze_binding_end_to_end(sample_repo, tmp_path, user, settings) -> None:
    settings.REPO_ALLOW_FILE_URLS = True
    settings.REPO_STORAGE_ROOT = tmp_path / "repos"
    binding = RepoBinding.objects.create(owner=user, repo_url=f"file://{sample_repo}")
    analyze_binding(binding)
    binding.refresh_from_db()
    assert binding.status == RepoStatus.READY, binding.error
    assert binding.summary["components"] >= 2
    assert binding.summary["patterns"] >= 2
    assert binding.index_path.is_file()


# Codebase page ------------------------------------------------------------------------


@pytest.mark.django_db
def test_adding_a_repository_queues_a_sealed_token_and_links_journeys(client, user) -> None:
    journey = Journey.objects.create(
        name="Staging journey",
        goal="Do the thing on staging.",
        start_url="https://staging.example.com/a",
        allowed_origins=["https://staging.example.com"],
        completion_policy={},
        evaluation_config={},
    )
    token = "github_pat_ABCDEFGHIJKLMNOPQRSTUV"
    with patch("apps.codebase.views.analyze_repository.delay") as delay:
        client.post(
            reverse("codebase:add"),
            {
                "repo_url": "https://github.com/owner/repo",
                "token": token,
                "live_site_url": "https://staging.example.com",
            },
        )
    binding = RepoBinding.objects.get()
    assert binding.owner == user
    sealed = delay.call_args.kwargs["credential_token"]
    assert token not in sealed and open_api_key(sealed) == token
    assert token not in json.dumps(binding.summary) + binding.error + binding.repo_url
    journey.refresh_from_db()
    assert journey.repo_binding == binding


@pytest.mark.django_db
def test_bad_repository_address_is_explained(client) -> None:
    response = client.post(
        reverse("codebase:add"), {"repo_url": "https://evil.example/a/b"}, follow=True
    )
    assert "Only github.com" in response.content.decode()
    assert RepoBinding.objects.count() == 0


@pytest.mark.django_db
def test_people_cannot_see_or_remove_each_others_repositories(client) -> None:
    other = get_user_model().objects.create_user("other", password="x")
    binding = RepoBinding.objects.create(owner=other, repo_url="https://github.com/o/secret-repo")
    page = client.get(reverse("codebase:page")).content.decode()
    assert "secret-repo" not in page
    assert client.post(reverse("codebase:remove", args=[binding.pk])).status_code == 404
    assert RepoBinding.objects.filter(pk=binding.pk).exists()
