from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from common.exceptions import LabBankAPIException

from .models import BlockedIdentifier


def _check_actor(actor) -> None:
    if (
        not actor
        or not actor.is_authenticated
        or not actor.is_active
        or not actor.groups.filter(name="manager").exists()
    ):
        raise PermissionDenied("An active manager is required.")


@transaction.atomic
def create_blocked_identifier(
    *,
    actor,
    kind: str,
    value: str,
    reason: str,
) -> BlockedIdentifier:
    """Block an identifier, raises 409 CONFLICT if an active record already exists"""
    _check_actor(actor)

    if BlockedIdentifier.objects.filter(kind=kind, value=value, active=True).exists():
        raise LabBankAPIException(
            code="CONFLICT",
            title="Resource conflict",
            detail="An active blocked identifier already exists.",
            status_code=status.HTTP_409_CONFLICT,
            type_slug="conflict",
        )

    try:
        with transaction.atomic():
            return BlockedIdentifier.objects.create(
                kind=kind,
                value=value,
                reason=reason,
                active=True,
                created_by=actor,
            )
    except IntegrityError as exc:
        raise LabBankAPIException(
            code="CONFLICT",
            title="Resource conflict",
            detail="An active blocked identifier already exists.",
            status_code=status.HTTP_409_CONFLICT,
            type_slug="conflict",
        ) from exc


@transaction.atomic
def deactivate_blocked_identifier(*, actor, identifier_id: UUID) -> BlockedIdentifier:
    """Soft-delete a blocked identifier while preserving audit fields"""
    _check_actor(actor)

    entry = BlockedIdentifier.objects.select_for_update().get(pk=identifier_id)
    if entry.active:
        entry.active = False
        entry.deactivated_at = timezone.now()
        entry.deactivated_by = actor
        entry.save(update_fields=["active", "deactivated_at", "deactivated_by"])
    return entry
