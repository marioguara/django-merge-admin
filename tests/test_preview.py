"""Scheda dei dati censiti su ciascun record da unire."""

import pytest
from django.contrib.auth.models import User

from merge_admin.preview import build_previews, preview_field_names

from .testapp.admin import ClienteAdmin
from .testapp.models import Cliente


@pytest.fixture
def clienti(db):
    a = Cliente.objects.create(nome="Giuseppe Verdi", codice="VRD58",
                               email="g.verdi@example.com", livello=2,
                               note="Cliente storico", interno="riservato")
    b = Cliente.objects.create(nome="Giuseppe V.", email="giuseppe@gmail.com")
    return [a, b]


def test_fields_follow_the_admin_fieldsets():
    """I campi tecnici fuori dai fieldsets non devono comparire."""
    admin = ClienteAdmin(Cliente, None)
    names = preview_field_names(Cliente, model_admin=admin)
    assert names == ["nome", "codice", "email", "livello", "note"]
    assert "interno" not in names


def test_without_an_admin_every_own_field_is_listed():
    names = preview_field_names(Cliente)
    assert "interno" in names
    assert "id" not in names


@pytest.mark.django_db
def test_preview_marks_the_fields_that_differ(clienti):
    a, b = clienti
    _names, righe = build_previews(Cliente, clienti, model_admin=ClienteAdmin(Cliente, None))
    diversi = {r["label"] for r in righe[a.pk] if r["differs"]}
    # Nome ed email cambiano; il livello è 2 contro il default 1.
    assert "Nome" in diversi
    assert "Email" in diversi
    # Il codice c'è solo su uno: un valore solo non è una differenza.
    assert "Codice" not in diversi


@pytest.mark.django_db
def test_preview_flags_empty_values(clienti):
    a, b = clienti
    _names, righe = build_previews(Cliente, clienti, model_admin=ClienteAdmin(Cliente, None))
    codice_b = next(r for r in righe[b.pk] if r["name"] == "codice")
    assert codice_b["empty"] is True
    assert codice_b["value"] is None


@pytest.mark.django_db
def test_preview_shows_readable_values(clienti):
    a, _b = clienti
    _names, righe = build_previews(Cliente, clienti, model_admin=ClienteAdmin(Cliente, None))
    livello = next(r for r in righe[a.pk] if r["name"] == "livello")
    assert livello["value"] == "Premium"     # l'etichetta, non il numero


@pytest.mark.django_db
def test_preview_shortens_very_long_values(clienti):
    a, _b = clienti
    a.note = "x" * 500
    a.save()
    _names, righe = build_previews(Cliente, clienti, max_length=40,
                                   model_admin=ClienteAdmin(Cliente, None))
    nota = next(r for r in righe[a.pk] if r["name"] == "note")
    assert len(nota["value"]) <= 40
    assert nota["value"].endswith("…")


@pytest.mark.django_db
def test_confirm_page_shows_each_record_data(client, clienti):
    a, b = clienti
    User.objects.create_superuser("capo", "capo@example.com", "x")
    client.login(username="capo", password="x")
    url = f"/admin/testapp/cliente/merge/confirm/?ids={a.pk}&ids={b.pk}"
    html = client.get(url).content.decode()

    assert "merge-admin-card" in html
    assert "g.verdi@example.com" in html and "giuseppe@gmail.com" in html
    assert "VRD58" in html
    assert "is-diff" in html                 # differenze evidenziate
    assert "riservato" not in html           # campo fuori dai fieldsets
    # La conferma non sta più in un onclick: l'apostrofo lo rompeva.
    assert "data-merge-confirm=" in html
    assert "onclick=\"return confirm" not in html
