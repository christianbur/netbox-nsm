from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel
from netbox.search import SearchIndex, register_search

__all__ = ("ObjectComment", "ObjectCommentIndex")


class ObjectComment(PrimaryModel):
    name = models.CharField(max_length=200, unique=True, verbose_name=_("Subject"))
    comment = models.TextField(blank=True, verbose_name=_("Comment"))

    class Meta:
        verbose_name = _("Comment Object")
        verbose_name_plural = _("Comment Objects")
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectcomment", args=[self.pk])


@register_search
class ObjectCommentIndex(SearchIndex):
    model = ObjectComment
    fields = (("name", 100), ("comment", 500), ("description", 500))
