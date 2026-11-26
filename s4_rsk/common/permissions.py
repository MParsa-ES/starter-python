from rest_framework.permissions import BasePermission


class IsRiskManager(BasePermission):
    """Management access is explicit group membership, not the staff flag."""

    message = "The manager role is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.groups.filter(name="manager").exists())


class IsPaymentService(BasePermission):
    """Only a separately provisioned payment service account may assess transfers."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active and user.groups.filter(name="payment_service").exists()
        )


class IsRiskOperator(BasePermission):
    """Manual review queue operations require explicit membership in the operator group."""

    message = "The operator role is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.groups.filter(name="operator").exists())

class CanReadDecisionHistory(BasePermission):
    """Allow active users in risk management/operations roles to read decision history"""

    allowed_groups = ("manager", "operator", "analyst")
    message = "A risk manager, operator, or analyst role is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.groups.filter(name__in=self.allowed_groups).exists()
        )
