from netbox.filtersets import PrimaryModelFilterSet
from utilities.filtersets import register_filterset

from netbox_nsm.models import ObjectComment

__all__ = ("ObjectCommentFilterSet",)


@register_filterset
class ObjectCommentFilterSet(PrimaryModelFilterSet):
    class Meta:
        model = ObjectComment
        fields = ("id", "name", "description")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value) | queryset.filter(comment__icontains=value)
