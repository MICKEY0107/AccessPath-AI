"""Model settings: choose a provider and model, and optionally remember an API key."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters

from engine.code_safety import code_safety
from engine.provider_models import ModelListError, list_models

from .credentials import (
    CredentialError,
    decrypt_saved_key,
    encrypt_saved_key,
    mask_api_key,
    validate_api_key,
    validate_model,
)
from .models import PlannerProvider, SavedCredential

LIVE_PROVIDERS = [
    PlannerProvider.GROQ,
    PlannerProvider.GEMINI,
    PlannerProvider.OPENROUTER,
    PlannerProvider.OLLAMA,
]

# Starting points; the List button shows what the provider really offers today.
RECOMMENDED_MODELS = {
    PlannerProvider.GROQ: [
        ("openai/gpt-oss-120b", "Passed the TodoMVC demo; strict JSON output"),
        ("openai/gpt-oss-20b", "Passed the Wikipedia demo; lower daily limit"),
        ("llama-3.3-70b-versatile", "General model; JSON mode"),
    ],
    PlannerProvider.GEMINI: [
        ("models/gemini-2.5-flash", "Fast general model"),
        ("models/gemini-2.5-flash-lite", "Cheaper, smaller"),
    ],
    PlannerProvider.OPENROUTER: [
        ("meta-llama/llama-3.3-70b-instruct", "Open general model"),
        ("openai/gpt-oss-120b", "Same model as on Groq"),
    ],
    PlannerProvider.OLLAMA: [
        ("llama3.1:8b", "Pull first: ollama pull llama3.1:8b"),
        ("qwen2.5:7b", "Pull first: ollama pull qwen2.5:7b"),
    ],
}


def server_key(provider: str) -> str:
    return {
        PlannerProvider.GEMINI: settings.GEMINI_API_KEY,
        PlannerProvider.OPENROUTER: settings.OPENROUTER_API_KEY,
        PlannerProvider.GROQ: settings.GROQ_API_KEY,
    }.get(provider, "")


def saved_for(user) -> dict[str, SavedCredential]:
    if not getattr(user, "is_authenticated", False):
        return {}
    return {item.provider: item for item in SavedCredential.objects.filter(owner=user)}


def saved_key(user, provider: str) -> str:
    """The person's remembered key for a provider, or "" when none is usable."""
    item = saved_for(user).get(provider)
    if item is None or not item.encrypted_key:
        return ""
    try:
        return decrypt_saved_key(item.encrypted_key)
    except CredentialError:
        return ""


def model_settings(request: HttpRequest) -> HttpResponse:
    saved = saved_for(request.user)
    preferred = next((item for item in saved.values() if item.is_preferred), None)
    cards = []
    for provider in LIVE_PROVIDERS:
        item = saved.get(provider)
        safety = code_safety(
            provider, item.default_model if item else "", settings.CODE_SAFE_PROVIDERS
        )
        cards.append(
            {
                "value": provider,
                "label": PlannerProvider(provider).label,
                "saved": item,
                "has_server_key": bool(server_key(provider)),
                "needs_key": provider != PlannerProvider.OLLAMA,
                "configured": provider != PlannerProvider.OLLAMA or bool(settings.OLLAMA_BASE_URL),
                "recommended": RECOMMENDED_MODELS[provider],
                "safety": safety,
            }
        )
    selected = request.GET.get("provider") or (
        preferred.provider if preferred else LIVE_PROVIDERS[0]
    )
    if selected not in LIVE_PROVIDERS:
        selected = LIVE_PROVIDERS[0]
    return render(
        request,
        "runs/model_settings.html",
        {"cards": cards, "selected": selected, "preferred": preferred},
    )


@sensitive_post_parameters("api_key")
def save_model_settings(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    provider = request.POST.get("provider", "")
    if provider not in LIVE_PROVIDERS:
        messages.error(request, "Choose one of the listed providers.")
        return redirect(reverse("runs:model_settings"))
    api_key = request.POST.get("api_key", "").strip()
    model = request.POST.get("model", "").strip()
    remember = request.POST.get("remember") == "on"
    problem = validate_api_key(api_key) if api_key else None
    if problem is None and model:
        problem = validate_model(model)
    if problem is None and provider == PlannerProvider.OLLAMA and api_key:
        problem = "Ollama runs locally and needs no API key."
    if problem:
        messages.error(request, problem)
        return redirect(f"{reverse('runs:model_settings')}?provider={provider}")
    item, _created = SavedCredential.objects.get_or_create(owner=request.user, provider=provider)
    item.default_model = model
    if api_key and remember:
        item.encrypted_key = encrypt_saved_key(api_key)
        item.key_hint = mask_api_key(api_key)
    elif api_key and not remember:
        messages.info(
            request,
            "The key was not remembered. Tick “Remember on this computer” to save it, "
            "or type it in the run form each time.",
        )
    SavedCredential.objects.filter(owner=request.user).update(is_preferred=False)
    item.is_preferred = True
    item.save()
    label = PlannerProvider(provider).label
    messages.success(
        request, f"Runs you start now default to {label}{f' · {model}' if model else ''}."
    )
    return redirect(f"{reverse('runs:model_settings')}?provider={provider}")


def forget_key(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    provider = request.POST.get("provider", "")
    updated = SavedCredential.objects.filter(owner=request.user, provider=provider).update(
        encrypted_key="", key_hint=""
    )
    if updated:
        messages.success(request, "The saved key was deleted.")
    return redirect(f"{reverse('runs:model_settings')}?provider={provider}")


@sensitive_post_parameters("api_key")
def list_provider_models(request: HttpRequest) -> HttpResponse:
    """Fetch the provider's model ids with the typed, saved, or server key."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    provider = request.POST.get("provider", "")
    if provider not in LIVE_PROVIDERS:
        return JsonResponse({"error": "Choose one of the listed providers."}, status=400)
    typed = request.POST.get("api_key", "").strip()
    if typed and validate_api_key(typed):
        return JsonResponse({"error": validate_api_key(typed)}, status=400)
    key = typed or saved_key(request.user, provider) or server_key(provider)
    try:
        models = list_models(provider, api_key=key, ollama_base_url=settings.OLLAMA_BASE_URL)
    except ModelListError as error:
        return JsonResponse({"error": str(error)}, status=502)
    return JsonResponse({"models": models})
