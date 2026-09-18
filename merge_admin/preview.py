"""Dati censiti su ciascun record, per poter scegliere quale conservare.

Sapere solo *quanti* oggetti collegati verranno spostati non basta: chi
decide vuole vedere i dati veri dei due record — telefono, email, data di
nascita — e soprattutto **dove differiscono**, perché è lì che si rischia di
perdere qualcosa unendo.
"""

from django.core.exceptions import FieldDoesNotExist
from django.db.models.fields.files import FieldFile
from django.utils.encoding import force_str
from django.utils.formats import localize


#: Oltre questa lunghezza il valore viene accorciato: la scheda deve restare
#: leggibile su un telefono.
DEFAULT_MAX_LENGTH = 140


def admin_field_names(model_admin):
    """I campi che l'admin stesso espone nei suoi fieldsets.

    Sono quelli che qualcuno ha scelto di curare: mostrarli evita di
    riempire la scheda di campi tecnici (token, contatori, flag interni) che
    a chi deve scegliere non dicono niente.
    """
    if model_admin is None:
        return []
    names = []
    fieldsets = getattr(model_admin, "fieldsets", None)
    if fieldsets:
        for _title, options in fieldsets:
            for entry in options.get("fields", ()) or ():
                if isinstance(entry, (list, tuple)):
                    names.extend(entry)
                else:
                    names.append(entry)
    elif getattr(model_admin, "fields", None):
        names = list(model_admin.fields)
    return names


def preview_field_names(model, explicit=None, model_admin=None):
    """Campi da mostrare nella scheda di un record.

    Ordine di scelta: quelli indicati esplicitamente, poi quelli esposti
    dall'admin, infine tutti i campi propri del modello.
    """
    if explicit:
        return list(explicit)

    concreti = {
        f.name
        for f in model._meta.get_fields()
        if getattr(f, "concrete", False) and not f.many_to_many
    }
    dai_fieldsets = [n for n in admin_field_names(model_admin) if n in concreti]
    if dai_fieldsets:
        # Un campo può comparire in più fieldsets: si tiene il primo posto.
        visti, ordinati = set(), []
        for n in dai_fieldsets:
            if n not in visti:
                visti.add(n)
                ordinati.append(n)
        return ordinati

    names = []
    for field in model._meta.get_fields():
        if not getattr(field, "concrete", False):
            continue
        if field.primary_key or field.auto_created or field.many_to_many:
            continue
        names.append(field.name)
    return names


def _raw_value(obj, name):
    field = None
    try:
        field = obj._meta.get_field(name)
    except FieldDoesNotExist:
        pass

    if field is not None and getattr(field, "choices", None):
        getter = getattr(obj, f"get_{name}_display", None)
        if getter:
            return getter()

    value = getattr(obj, name, None)

    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "Sì" if value else "No"
    if isinstance(value, FieldFile):
        # FileField / ImageField: interessa il nome del file, non l'oggetto.
        return value.name or None
    return value


def _label_for(model, name):
    try:
        field = model._meta.get_field(name)
    except FieldDoesNotExist:
        attr = getattr(model, name, None)
        return force_str(getattr(attr, "short_description", name)).capitalize()
    return force_str(getattr(field, "verbose_name", name)).capitalize()


def _display(value, max_length):
    if value is None:
        return None
    text = force_str(localize(value)).strip()
    if not text:
        return None
    if len(text) > max_length:
        text = text[: max_length - 1].rstrip() + "…"
    return text


def build_previews(model, objects, field_names=None, max_length=DEFAULT_MAX_LENGTH,
                   model_admin=None):
    """Per ogni record, l'elenco dei suoi dati, con i diversi evidenziati.

    Restituisce ``(nomi_campi, {pk: [riga, ...]})`` dove ogni riga è
    ``{"name", "label", "value", "empty", "differs"}``. ``differs`` è vero
    quando quel campo non ha lo stesso valore su tutti i record in gioco: è
    il segnale che guida la scelta.
    """
    names = preview_field_names(model, field_names, model_admin=model_admin)
    valori = {}
    for obj in objects:
        valori[obj.pk] = {n: _display(_raw_value(obj, n), max_length) for n in names}

    # Un campo "differisce" se i valori presenti non sono tutti uguali.
    diversi = set()
    for name in names:
        presenti = {valori[o.pk][name] for o in objects if valori[o.pk][name] is not None}
        if len(presenti) > 1:
            diversi.add(name)

    righe = {}
    for obj in objects:
        righe[obj.pk] = [
            {
                "name": name,
                "label": _label_for(model, name),
                "value": valori[obj.pk][name],
                "empty": valori[obj.pk][name] is None,
                "differs": name in diversi,
            }
            for name in names
        ]
    return names, righe
