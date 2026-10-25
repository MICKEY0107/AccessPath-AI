from django.shortcuts import render


def home(request):
    """Render the accessible project landing page."""
    return render(request, "core/home.html")
