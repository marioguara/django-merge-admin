from django.contrib import admin

from merge_admin.mixins import MergeAdminMixin

from .models import Cliente, Ordine


@admin.register(Cliente)
class ClienteAdmin(MergeAdminMixin, admin.ModelAdmin):
    search_fields = ("nome", "codice")
    # Il campo "interno" resta fuori dai fieldsets: la scheda di unione non
    # deve mostrarlo, perché non è un dato che qualcuno cura a mano.
    fieldsets = (
        ("Anagrafica", {"fields": (("nome", "codice"), "email")}),
        ("Altro", {"fields": ("livello", "note")}),
    )


admin.site.register(Ordine)
