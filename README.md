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

| Attribute | Type | Default | Meaning |
|-----------|------|---------|---------|
| `merge_excluded_relations` | tuple[str] | `()` | Reverse accessor names to leave untouched. |
| `merge_fill_empty_fields` | bool | `True` | Fill blank primary fields from duplicates. |
| `merge_search_fields` | tuple[str] \| None | `None` | Fields used by the picker AJAX search. Defaults to `search_fields`. |
| `merge_action_label` | str | *"Unisci selezionati…"* | Label of the changelist action. |
| `merge_button_label` | str | *"Unisci con…"* | Label of the button in the change view. |

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
