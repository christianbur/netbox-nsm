import re

from django import forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe


class ColorSelectTextWidget(forms.TextInput):
    """Render a color picker alongside a plain HTML color code input."""

    def __init__(self, attrs=None):
        default_attrs = {
            "maxlength": 7,
            "placeholder": "#aabbcc",
            "pattern": "^#[0-9a-fA-F]{6}$",
            "spellcheck": "false",
            "style": "max-width: 8rem;",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def render(self, name, value, attrs=None, renderer=None):
        value = (value or "").strip()
        text_attrs = (attrs or {}).copy()
        input_id = text_attrs.get("id") or self.attrs.get("id") or f"id_{name}"
        text_style = text_attrs.get("style", "")
        text_attrs["id"] = input_id
        text_attrs["maxlength"] = 7
        text_attrs["placeholder"] = "#aabbcc"
        text_attrs["pattern"] = "^#[0-9a-fA-F]{6}$"
        text_attrs["spellcheck"] = "false"
        text_attrs["style"] = "; ".join(
            part for part in (text_style, "max-width: 8rem;") if part
        )
        text_attrs["oninput"] = (
            f"var picker=document.getElementById('{input_id}__picker');"
            "if(picker && /^#[0-9a-fA-F]{6}$/.test(this.value)){picker.value=this.value;}"
        )

        picker_value = value if re.match(r"^#[0-9a-fA-F]{6}$", value) else "#000000"
        picker_html = format_html(
            '<input type="color" class="form-control form-control-color" '
            'id="{}__picker" value="{}" style="width: 3rem; min-width: 3rem; padding: 0.125rem;" '
            "oninput=\"document.getElementById('{}').value = this.value;\">",
            input_id,
            picker_value,
            input_id,
        )
        text_html = super().render(name, value, text_attrs, renderer)
        return format_html(
            '<div class="d-flex align-items-center gap-2">{}{}</div>',
            picker_html,
            mark_safe(text_html),
        )
