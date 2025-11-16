"""
Context processors for admin panel
Provides global context variables available in all templates
"""

from django.db.models import F
from storefront.models import Appeal, Product


def admin_context(request):
    """Add admin-specific context variables to all templates"""
    context = {}

    # Add pending appeals count for sidebar badge
    if request.user.is_authenticated and (
        request.user.is_staff
        or request.user.is_superuser
        or getattr(request.user, "role", None) == "admin"
    ):
        context["pending_appeals_count"] = Appeal.objects.filter(
            status="pending"
        ).count()

        # Add low-stock count for sidebar badge (stock < reorder_threshold)
        context["low_stock_count"] = Product.objects.filter(
            stock__lt=F("reorder_threshold")
        ).count()

    return context
