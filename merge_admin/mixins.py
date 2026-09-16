"""Reusable admin mixin exposing merge-records functionality.

Add ``MergeAdminMixin`` to any ``ModelAdmin`` to get:

* A changelist action ("Unisci selezionati…") that opens a confirmation page
  where the user picks which of the selected records to keep.
* A per-object "Unisci con…" button in the object-tools bar of the change
  view (next to *History*), letting the user pick a second record to merge
  with the current one.
* AJAX search endpoint used by the picker.

The mixin is model-agnostic: it discovers reverse relations at runtime via
``utils.build_plan`` / ``utils.merge_records``.
"""
from __future__ import annotations

from typing import Optional, Tuple

from django.contrib import messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _

from .utils import build_plan, merge_records


class MergeAdminMixin:
    change_form_template = "merge_admin/change_form.html"

    merge_excluded_relations: Tuple[str, ...] = ()
    merge_fill_empty_fields: bool = True
    merge_search_fields: Optional[Tuple[str, ...]] = None
    merge_action_label = _("Unisci selezionati…")
    merge_button_label = _("Unisci con…")

    # ------------------------------------------------------------------ helpers

    def _merge_search_fields(self):
        return self.merge_search_fields or getattr(self, "search_fields", ()) or ()

    def _info(self):
        return self.model._meta.app_label, self.model._meta.model_name

    # -------------------------------------------------------------------- urls

    def get_urls(self):
        urls = super().get_urls()
        info = self._info()
        custom = [
            path(
                "merge/confirm/",
                self.admin_site.admin_view(self.merge_confirm_view),
                name="%s_%s_merge_confirm" % info,
            ),
            path(
                "merge/search/",
                self.admin_site.admin_view(self.merge_search_view),
                name="%s_%s_merge_search" % info,
            ),
            path(
                "<path:object_id>/merge/",
                self.admin_site.admin_view(self.merge_from_object_view),
                name="%s_%s_merge_from_object" % info,
            ),
        ]
        return custom + urls

    # ------------------------------------------------------------ change view

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = dict(extra_context or {})
        info = self._info()
        extra_context["merge_admin_from_object_url"] = reverse(
            "admin:%s_%s_merge_from_object" % info, args=[object_id]
        )
        extra_context["merge_admin_button_label"] = self.merge_button_label
        return super().change_view(request, object_id, form_url, extra_context)

    # -------------------------------------------------------- changelist action

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions["merge_selected"] = (
            self.__class__.merge_selected,
            "merge_selected",
            str(self.merge_action_label),
        )
        return actions

    def merge_selected(self, request, queryset):
        pks = list(queryset.values_list("pk", flat=True))
        if len(pks) < 2:
            self.message_user(
                request,
                _("Seleziona almeno 2 record per poterli unire."),
                level=messages.WARNING,
            )
            return None
        info = self._info()
        url = reverse("admin:%s_%s_merge_confirm" % info)
        query = "&".join("ids=%s" % pk for pk in pks)
        return redirect("%s?%s" % (url, query))

    merge_selected.short_description = _("Unisci selezionati…")

    # ------------------------------------------------------ from-object picker

    def merge_from_object_view(self, request, object_id):
        obj = get_object_or_404(self.model, pk=object_id)
        info = self._info()
        context = self.admin_site.each_context(request)
        context.update({
            "opts": self.model._meta,
            "original": obj,
            "title": _("Unisci %s con…") % obj,
            "search_url": reverse("admin:%s_%s_merge_search" % info),
            "confirm_url": reverse("admin:%s_%s_merge_confirm" % info),
            "current_id": obj.pk,
            "cancel_url": reverse("admin:%s_%s_change" % info, args=[obj.pk]),
        })
        return render(request, "merge_admin/select.html", context)

    # -------------------------------------------------------- ajax search endpoint

    def merge_search_view(self, request):
        q = (request.GET.get("q") or "").strip()
        exclude = request.GET.get("exclude", "")
        qs = self.get_queryset(request)
        if exclude:
            qs = qs.exclude(pk=exclude)
        search_fields = self._merge_search_fields()
        if q and search_fields:
            filters = Q()
            for f in search_fields:
                filters |= Q(**{f + "__icontains": q})
            qs = qs.filter(filters)
        qs = qs[:20]
        return JsonResponse({
            "results": [{"id": obj.pk, "text": str(obj)} for obj in qs],
        })

    # -------------------------------------------------------- confirmation view

    def _resolve_ids(self, request):
        raw = request.GET.getlist("ids") or request.POST.getlist("ids")
        if not raw and ACTION_CHECKBOX_NAME in request.POST:
            raw = request.POST.getlist(ACTION_CHECKBOX_NAME)
        try:
            ids = [int(x) for x in raw if x]
        except (TypeError, ValueError):
            raise Http404
        seen = set()
        ordered = []
        for i in ids:
            if i in seen:
                continue
            seen.add(i)
            ordered.append(i)
        return ordered

    def merge_confirm_view(self, request):
        ids = self._resolve_ids(request)
        info = self._info()
        if len(ids) < 2:
            self.message_user(
                request,
                _("Servono almeno 2 record da unire."),
                level=messages.WARNING,
            )
            return redirect("admin:%s_%s_changelist" % info)

        objects = list(self.model._default_manager.filter(pk__in=ids))
        order = {pk: i for i, pk in enumerate(ids)}
        objects.sort(key=lambda o: order.get(o.pk, 0))
        if len(objects) < 2:
            self.message_user(
                request,
                _("Almeno un record non è stato trovato."),
                level=messages.ERROR,
            )
            return redirect("admin:%s_%s_changelist" % info)

        primary_id = request.POST.get("primary")
        if request.method == "POST" and request.POST.get("confirm") and primary_id:
            try:
                primary_id_int = int(primary_id)
            except (TypeError, ValueError):
                primary_id_int = None
            primary = next((o for o in objects if o.pk == primary_id_int), None)
            if primary is None:
                self.message_user(request, _("Record da conservare non valido."), level=messages.ERROR)
            else:
                duplicates = [o for o in objects if o.pk != primary.pk]
                plan = merge_records(
                    primary,
                    duplicates,
                    excluded_relations=self.merge_excluded_relations,
                    fill_empty_fields=self.merge_fill_empty_fields,
                )
                self.message_user(
                    request,
                    _(
                        "Uniti %(dups)d record in «%(primary)s». "
                        "Spostati %(related)d oggetti collegati."
                    ) % {
                        "dups": len(plan.duplicate_pks),
                        "primary": str(primary),
                        "related": plan.total_related,
                    },
                    level=messages.SUCCESS,
                )
                return redirect("admin:%s_%s_change" % info, primary.pk)

        previews = []
        for candidate in objects:
            duplicates = [o for o in objects if o.pk != candidate.pk]
            preview = build_plan(
                candidate,
                duplicates,
                excluded_relations=self.merge_excluded_relations,
                fill_empty_fields=self.merge_fill_empty_fields,
            )
            previews.append({"obj": candidate, "plan": preview})

        context = self.admin_site.each_context(request)
        context.update({
            "opts": self.model._meta,
            "title": _("Unisci %(model)s") % {"model": self.model._meta.verbose_name_plural},
            "objects": objects,
            "previews": previews,
            "ids": ids,
            "cancel_url": reverse("admin:%s_%s_changelist" % info),
            "action_url": reverse("admin:%s_%s_merge_confirm" % info),
        })
        return render(request, "merge_admin/confirm.html", context)
