"""Unione dei record: cosa si sposta, cosa si travasa, cosa si rompeva."""

import pytest
from django.contrib.auth.models import User

from merge_admin.utils import build_plan, merge_records

from .testapp.models import Cliente, Ordine


@pytest.fixture
def coppia(db):
    """Due record dello stesso cliente: uno completo, uno arrivato dopo."""
    pieno = Cliente.objects.create(
        nome="Giuseppe Verdi", codice="VRD58", email="g.verdi@example.com",
        livello=2, note="Cliente storico",
    )
    scarno = Cliente.objects.create(nome="Giuseppe V.", email="giuseppe@gmail.com")
    Ordine.objects.create(cliente=pieno, numero="A-1")
    Ordine.objects.create(cliente=scarno, numero="B-1")
    Ordine.objects.create(cliente=scarno, numero="B-2")
    return pieno, scarno


@pytest.mark.django_db
def test_merge_moves_related_objects(coppia):
    pieno, scarno = coppia
    merge_records(pieno, [scarno])
    assert set(pieno.ordini.values_list("numero", flat=True)) == {"A-1", "B-1", "B-2"}
    assert not Cliente.objects.filter(pk=scarno.pk).exists()


@pytest.mark.django_db
def test_merge_fills_a_unique_field_without_breaking(coppia):
    """Regressione: il travaso avveniva prima di eliminare il duplicato.

    Copiare un valore di un campo `unique` mentre il duplicato è ancora nel
    database violava il vincolo, e l'unione falliva con IntegrityError —
    proprio nel caso più comune, cioè conservare il record più recente.
    """
    pieno, scarno = coppia
    merge_records(scarno, [pieno])          # si conserva quello SENZA codice
    scarno.refresh_from_db()
    assert scarno.codice == "VRD58"
    assert scarno.note == "Cliente storico"
    assert not Cliente.objects.filter(pk=pieno.pk).exists()
    assert scarno.ordini.count() == 3


@pytest.mark.django_db
def test_merge_keeps_its_own_values(coppia):
    """Il travaso riempie solo i buchi, non sovrascrive niente."""
    pieno, scarno = coppia
    merge_records(scarno, [pieno])
    scarno.refresh_from_db()
    assert scarno.email == "giuseppe@gmail.com"
    assert scarno.nome == "Giuseppe V."


@pytest.mark.django_db
def test_without_deleting_duplicates_unique_fields_are_left_alone(coppia):
    """Senza eliminare i duplicati il valore unico resta occupato: si salta."""
    pieno, scarno = coppia
    merge_records(scarno, [pieno], delete_duplicates=False)
    scarno.refresh_from_db()
    assert scarno.codice is None            # saltato, non copiato
    assert scarno.note == "Cliente storico"  # gli altri campi sì
    assert Cliente.objects.filter(pk=pieno.pk).exists()


@pytest.mark.django_db
def test_plan_counts_what_will_move(coppia):
    pieno, scarno = coppia
    # Conservando quello completo si spostano solo gli ordini dell'altro.
    plan = build_plan(pieno, [scarno])
    assert plan.total_related == 2
    assert plan.field_fills == []
    # Conservando quello scarno, invece, c'è anche da travasare.
    plan = build_plan(scarno, [pieno])
    assert "codice" in plan.field_fills
