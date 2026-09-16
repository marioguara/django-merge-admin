# django-merge-admin

Reusable Django admin mixin to safely merge two or more model records into one, re-parenting every related object (reverse ForeignKey, OneToOne, ManyToMany) to the surviving record before the duplicates are deleted — all in a single DB transaction.

Works on any `ModelAdmin`, on any model. Zero configuration required; every hook is optional.

## Features

- Changelist action **"Unisci selezionati…"** with a confirmation page that shows exactly what will be moved for each candidate primary.
- **"Unisci con…"** button on the object-tools bar of the change view (next to *History*), with a live search picker to choose the second record.
- Reflective merge: discovers reverse relations at runtime, no model-specific code needed.
- Optional back-fill: copies non-empty field values from duplicates into blank fields of the primary.
- Fully translatable (Italian strings shipped, `gettext_lazy` throughout).

## Install

```bash
pip install django-merge-admin
```

Add to `INSTALLED_APPS` **before** `django.contrib.admin` is not required — the app only ships templates and static, no models:

```python
INSTALLED_APPS = [
    # ...
    "django.contrib.admin",
    "merge_admin",
    # ...
]
```

## Usage

```python
from django.contrib import admin
from merge_admin.mixins import MergeAdminMixin
from myapp.models import Customer

@admin.register(Customer)
class CustomerAdmin(MergeAdminMixin, admin.ModelAdmin):
    search_fields = ["email", "name"]           # used by the merge picker

    # optional
    merge_excluded_relations = ("logentry_set",)  # accessors to skip
    merge_fill_empty_fields = True                # default
```

If your admin already sets `change_form_template`, extend `merge_admin/change_form.html` instead of `admin/change_form.html`:

```html
{% extends "merge_admin/change_form.html" %}
```

## Configuration

Every option is a class attribute on your `ModelAdmin`. All are optional.

### `merge_excluded_relations`
- **Type:** `tuple[str]`
- **Default:** `()`
- **What it does:** Reverse accessor names that the merge **must not touch**. The related objects on those relations remain on the duplicates and are cascade-deleted with them.
- **Why you'd set it:** to preserve audit trails or system data that is meaningful only for the record it was originally attached to.
- **Example:** `merge_excluded_relations = ("logentry", "auditrecord_set")` — Django admin log entries and your custom audit records stay with the deleted duplicates instead of being reassigned to the primary.

### `merge_fill_empty_fields`
- **Type:** `bool`
- **Default:** `True`
- **What it does:** After relations are re-parented, walks every scalar (non-relation, non-PK) field on the primary. Any field whose value is `None` or `""` is filled with the first non-empty value found on a duplicate, following the order of the duplicates list. **Existing values on the primary are never overwritten**, only blanks are filled.
- **Why you'd set it to `False`:** when the primary is the canonical record and you don't want any data from duplicates leaking into it — the duplicates are only present as bad rows to remove; keep the primary bit-for-bit identical.
- **Example:** primary has `email` but no `phone`, duplicate has `phone` — with the default `True` the merged primary ends up with both. With `False` the primary stays without `phone`.

### `merge_search_fields`
- **Type:** `tuple[str] | None`
- **Default:** `None`
- **What it does:** Fields used by the live-search picker (the AJAX endpoint behind the "Merge with…" button). Falls back to your admin's `search_fields` when `None`, so most projects can ignore this.
- **Why you'd set it:** when your admin `search_fields` are optimized for the changelist search box but you want a different (usually narrower) match for the merge picker — e.g. match only on unique identifiers to avoid picking the wrong record.
- **Example:** `merge_search_fields = ("email", "codice_fiscale")` — the merge picker only matches on those two, even though the changelist search also looks at names.

### `merge_action_label`
- **Type:** `str` (translatable)
- **Default:** *"Unisci selezionati…"*
- **What it does:** Label shown in the changelist action dropdown for the bulk-merge action.
- **Example:** `merge_action_label = "Merge selected customers…"`

### `merge_button_label`
- **Type:** `str` (translatable)
- **Default:** *"Unisci con…"*
- **What it does:** Label of the object-tools button that appears in the change view, next to *History*, opening the picker to choose a partner record to merge with.
- **Example:** `merge_button_label = "Merge with…"`

### Full example

```python
from django.contrib import admin
from merge_admin.mixins import MergeAdminMixin
from myapp.models import Customer

@admin.register(Customer)
class CustomerAdmin(MergeAdminMixin, admin.ModelAdmin):
    search_fields = ["email", "name"]

    merge_excluded_relations = ("logentry", "auditrecord_set")
    merge_fill_empty_fields = True
    merge_search_fields = ("email", "vat_number")
    merge_action_label = "Merge selected customers…"
    merge_button_label = "Merge with…"
```

## Programmatic API

```python
from merge_admin.utils import merge_records, build_plan

plan = build_plan(primary, duplicates)
print(plan.total_related, plan.relations, plan.field_fills)

merge_records(primary, duplicates)     # atomic
```

## Compatibility

- Python 3.8+
- Django 3.2 – 5.2

## License

MIT
