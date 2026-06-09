"""Next free rule index for deployed COT rulebooks."""

from __future__ import annotations

from django.db.models import Max

__all__ = ("next_rulebook_index",)


def next_rulebook_index(cot) -> int:
    """Return the next free rule index (1, 2, 3, …)."""
    model = cot.get_model()
    max_idx = model.objects.aggregate(m=Max("index"))["m"]
    if max_idx is None:
        return 1
    return max_idx + 1
