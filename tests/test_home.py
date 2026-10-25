from django.urls import reverse


def test_homepage_is_available_and_has_main_landmark(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert 'id="main-content"' in response.content.decode()
    assert "keyboard-only motor accessibility" in response.content.decode().lower()
