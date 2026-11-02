from rest_framework.permissions import BasePermission


class IsRiskManager(BasePermission):
    """Management access is explicit group membership, not the staff flag."""

    message = "The manager role is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.groups.filter(name="manager").exists()
        )
