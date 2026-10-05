"""Compare normalized form data before a ModelForm mutates its instance."""

from django import forms


def snapshot_form_values(form):
    values = {}
    for name, field in form.fields.items():
        if not hasattr(form.instance, name):
            continue
        if isinstance(field, forms.ModelChoiceField):
            values[name] = getattr(form.instance, f"{name}_id")
        else:
            values[name] = getattr(form.instance, name)
    return values


def form_values_changed(before, form):
    for name, previous in before.items():
        value = form.cleaned_data.get(name)
        field = form.fields[name]
        if isinstance(field, forms.ModelChoiceField):
            value = value.pk if value is not None else None
        if value != previous:
            return True
    return False
