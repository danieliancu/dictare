import pytest
from django.contrib import admin
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_every_admin_changelist_and_add_page_loads(client, phrases, plans):
    superuser = User.objects.create_superuser(email="admin@example.com", password="x-admin-123")
    client.force_login(superuser)
    for model, model_admin in admin.site._registry.items():
        meta = model._meta
        url = reverse(f"admin:{meta.app_label}_{meta.model_name}_changelist")
        assert client.get(url).status_code == 200, url
        if model_admin.has_add_permission(type("R", (), {"user": superuser})()):
            add = reverse(f"admin:{meta.app_label}_{meta.model_name}_add")
            assert client.get(add).status_code == 200, add


@pytest.mark.django_db
def test_phrase_change_page_and_generate_audio_action(client, phrases, plans):
    superuser = User.objects.create_superuser(email="admin@example.com", password="x-admin-123")
    client.force_login(superuser)
    url = reverse("admin:listening_listeningphrase_change", args=[phrases[0].pk])
    assert client.get(url).status_code == 200
    response = client.post(
        reverse("admin:listening_listeningphrase_changelist"),
        {"action": "generate_audio", "_selected_action": [phrases[0].pk]},
    )
    assert response.status_code == 302
    assert phrases[0].audio_variants.count() == 3


@pytest.mark.django_db
def test_attempts_are_read_only_in_admin(client, plans):
    superuser = User.objects.create_superuser(email="admin@example.com", password="x-admin-123")
    client.force_login(superuser)
    assert client.get(reverse("admin:practice_listeningattempt_add")).status_code == 403
