"""
Reflective merge logic.

Given a ``primary`` instance and one or more ``duplicates`` of the same model,
re-parent every related object (reverse FK, reverse/forward O2O, M2M) that
currently points to a duplicate so that it points to ``primary``, then delete
the duplicates. Optionally copy field values from duplicates into empty fields
of the primary.

The whole operation runs inside a single DB transaction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence

from django.db import transaction
from django.db.models import (
    ManyToManyField,
    Model,
    OneToOneRel,
    ManyToOneRel,
    ManyToManyRel,
)


@dataclass
class RelationPlan:
    label: str
    model_label: str
    count: int
    kind: str  # 'fk' | 'o2o' | 'm2m'


@dataclass
class MergePlan:
    primary_pk: object
    duplicate_pks: List[object]
    relations: List[RelationPlan] = field(default_factory=list)
    field_fills: List[str] = field(default_factory=list)

    @property
    def total_related(self) -> int:
        return sum(r.count for r in self.relations)


def _reverse_descriptors(model):
    """Yield ``(rel, kind, accessor)`` for reverse FK / O2O / M2M relations.

    ``rel`` is the reverse ``*Rel`` object; ``rel.field`` is the concrete
    field on the *other* model.
    """
    for rel in model._meta.get_fields(include_hidden=False):
        if not getattr(rel, "auto_created", False) or getattr(rel, "concrete", False):
            continue
        # order matters: ManyToManyRel and OneToOneRel both subclass ManyToOneRel
        if isinstance(rel, ManyToManyRel):
            kind = "m2m_reverse"
        elif isinstance(rel, OneToOneRel):
            kind = "o2o"
        elif isinstance(rel, ManyToOneRel):
            kind = "fk"
        else:
            continue
        yield rel, kind, rel.get_accessor_name()


def _forward_m2m(model):
    """Yield ``(field, accessor)`` for M2M declared on ``model`` itself."""
    for f in model._meta.local_many_to_many:
        yield f, f.name


def _m2m_through_columns(m2m_field, source_is_local):
    """Return ``(source_attr, target_attr)`` for the through model.

    ``source_attr`` is the attribute of the through model pointing to the
    side we are re-parenting (i.e. the merged model). When the M2M is
    declared *on* the merged model, that's ``m2m_field_name()``. When we
    reach the M2M through the reverse descriptor, it's the opposite.
    """
    if source_is_local:
        return m2m_field.m2m_field_name(), m2m_field.m2m_reverse_field_name()
    return m2m_field.m2m_reverse_field_name(), m2m_field.m2m_field_name()


def build_plan(
    primary: Model,
    duplicates: Sequence[Model],
    excluded_relations: Iterable[str] = (),
    fill_empty_fields: bool = True,
) -> MergePlan:
    """Inspect the relations and produce a MergePlan describing what will move."""
    if not duplicates:
        raise ValueError("At least one duplicate is required.")
    model = type(primary)
    for dup in duplicates:
        if type(dup) is not model:
            raise ValueError("All records to merge must be of the same model.")
        if dup.pk == primary.pk:
            raise ValueError("Duplicate list must not contain the primary record.")

    excluded = set(excluded_relations or [])
    plan = MergePlan(primary_pk=primary.pk, duplicate_pks=[d.pk for d in duplicates])
    dup_pks = plan.duplicate_pks

    # Reverse FK / O2O / M2M
    for rel, kind, accessor in _reverse_descriptors(model):
        if accessor in excluded:
            continue
        related_model = rel.related_model
        remote_field = rel.field

        if kind in ("fk", "o2o"):
            qs = related_model._default_manager.filter(**{remote_field.name + "__in": dup_pks})
            count = qs.count()
            display_kind = kind
        else:  # m2m_reverse
            through = remote_field.remote_field.through
            src, _tgt = _m2m_through_columns(remote_field, source_is_local=False)
            qs = through._default_manager.filter(**{src + "__in": dup_pks})
            count = qs.count()
            display_kind = "m2m"

        if count:
            plan.relations.append(RelationPlan(
                label=accessor,
                model_label=f"{related_model._meta.app_label}.{related_model.__name__}",
                count=count,
                kind=display_kind,
            ))

    # Forward M2M (declared on the merged model)
    for m2m_field, accessor in _forward_m2m(model):
        if accessor in excluded:
            continue
        through = m2m_field.remote_field.through
        src, _tgt = _m2m_through_columns(m2m_field, source_is_local=True)
        qs = through._default_manager.filter(**{src + "__in": dup_pks})
        count = qs.count()
        if count:
            plan.relations.append(RelationPlan(
                label=accessor,
                model_label=f"{m2m_field.related_model._meta.app_label}.{m2m_field.related_model.__name__}",
                count=count,
                kind="m2m",
            ))

    if fill_empty_fields:
        for f in model._meta.get_fields():
            if not getattr(f, "concrete", False):
                continue
            if f.primary_key or f.auto_created:
                continue
            if isinstance(f, ManyToManyField):
                continue
            if not hasattr(f, "attname"):
                continue
            current = getattr(primary, f.attname, None)
            if current in (None, ""):
                for dup in duplicates:
                    val = getattr(dup, f.attname, None)
                    if val not in (None, ""):
                        plan.field_fills.append(f.name)
                        break

    return plan


def _reparent_m2m(through, source_attr, target_attr, primary_pk, dup_pks):
    """Move through-rows from duplicates to primary, dropping already-present targets."""
    dup_qs = through._default_manager.filter(**{source_attr + "__in": dup_pks})
    target_pks = list(dup_qs.values_list(target_attr, flat=True).distinct())
    dup_qs.delete()
    existing = set(
        through._default_manager
        .filter(**{source_attr: primary_pk})
        .values_list(target_attr, flat=True)
    )
    to_add = [t for t in target_pks if t not in existing]
    if to_add:
        through._default_manager.bulk_create([
            through(**{source_attr + "_id": primary_pk, target_attr + "_id": t})
            for t in to_add
        ])


@transaction.atomic
def merge_records(
    primary: Model,
    duplicates: Sequence[Model],
    *,
    excluded_relations: Iterable[str] = (),
    fill_empty_fields: bool = True,
    delete_duplicates: bool = True,
) -> MergePlan:
    """Perform the merge. Returns the plan that was applied."""
    plan = build_plan(
        primary,
        duplicates,
        excluded_relations=excluded_relations,
        fill_empty_fields=fill_empty_fields,
    )
    model = type(primary)
    dup_pks = plan.duplicate_pks
    excluded = set(excluded_relations or [])

    # Reverse FK / O2O / M2M
    for rel, kind, accessor in _reverse_descriptors(model):
        if accessor in excluded:
            continue
        related_model = rel.related_model
        remote_field = rel.field

        if kind == "fk":
            related_model._default_manager.filter(
                **{remote_field.name + "__in": dup_pks}
            ).update(**{remote_field.name: primary.pk})

        elif kind == "o2o":
            already = related_model._default_manager.filter(
                **{remote_field.name: primary.pk}
            ).exists()
            qs = related_model._default_manager.filter(**{remote_field.name + "__in": dup_pks})
            if already:
                qs.delete()
            else:
                first = qs.order_by("pk").first()
                if first is not None:
                    setattr(first, remote_field.name, primary)
                    first.save(update_fields=[remote_field.name])
                    related_model._default_manager.filter(
                        **{remote_field.name + "__in": dup_pks}
                    ).exclude(pk=first.pk).delete()

        else:  # reverse M2M
            through = remote_field.remote_field.through
            src, tgt = _m2m_through_columns(remote_field, source_is_local=False)
            _reparent_m2m(through, src, tgt, primary.pk, dup_pks)

    # Forward M2M
    for m2m_field, accessor in _forward_m2m(model):
        if accessor in excluded:
            continue
        through = m2m_field.remote_field.through
        src, tgt = _m2m_through_columns(m2m_field, source_is_local=True)
        _reparent_m2m(through, src, tgt, primary.pk, dup_pks)

    # Valori da travasare nei campi vuoti del record che sopravvive.
    # Si leggono adesso, dagli oggetti gia' in memoria, ma si scrivono DOPO
    # aver eliminato i duplicati: copiare prima un valore di un campo unique
    # (un codice fiscale, una email) violerebbe il vincolo, perche' quel
    # valore appartiene ancora al duplicato.
    fills = {}
    if fill_empty_fields and plan.field_fills:
        for name in plan.field_fills:
            if getattr(primary, name, None) not in (None, ""):
                continue
            for dup in duplicates:
                val = getattr(dup, name, None)
                if val not in (None, ""):
                    fills[name] = val
                    break

    if delete_duplicates:
        model._default_manager.filter(pk__in=dup_pks).delete()
    elif fills:
        # Senza eliminare i duplicati, un valore unico resta occupato:
        # quei campi si lasciano com'erano invece di far fallire tutto.
        fills = {
            name: value
            for name, value in fills.items()
            if not getattr(model._meta.get_field(name), "unique", False)
        }

    if fills:
        for name, value in fills.items():
            setattr(primary, name, value)
        primary.save(update_fields=list(fills))

    return plan
