"""
Context processors for admin panel
Provides global context variables available in all templates
"""

from storefront.models import Appeal


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

    return context
