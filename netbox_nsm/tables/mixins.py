from django.utils.html import format_html


class AssignedObjectParentMixin:
    """
    Renders the assigned_object_parent column as
    "{ModelVerboseName} / <linked parent>" so the user sees the full path,
    e.g. "Interface / dmi01-albany-pdu01" instead of just "dmi01-albany-pdu01".

    Requires that the table column uses
        accessor=tables.A("assigned_object__device")
    (or any FK that serves as the parent object).
    """

    def render_assigned_object_parent(self, record, value):
        # Friendly model type name from the GFK content type
        ct = getattr(record, "assigned_object_type", None)
        if ct:
            model_class = ct.model_class()
            if model_class:
                type_label = model_class._meta.verbose_name_plural.title()
            else:
                type_label = f"{ct.app_label}.{ct.model}"
        else:
            type_label = "—"

        if value:
            return format_html(
                "{} / <a href=\"{}\">{}</a>",
                type_label,
                value.get_absolute_url(),
                str(value),
            )
        return type_label
