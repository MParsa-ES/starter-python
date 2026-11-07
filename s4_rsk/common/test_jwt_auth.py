from datetime import timedelta

import jwt
import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken


@pytest.mark.django_db
def test_jwt_login_permissions_rotation_and_logout(django_user_model):
    user = django_user_model.objects.create_user("manager", password="example-password-123")
    user.groups.add(Group.objects.create(name="manager"))
    client = APIClient()
    assert client.get("/api/v1/risk-rules").status_code == 401
    login = client.post(
        "/api/v1/auth/token/", {"username": "manager", "password": "example-password-123"}, format="json"
    )
    assert login.status_code == 200
    tokens = login.json()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert client.get("/api/v1/risk-rules").status_code == 200
    assert client.get("/api/v1/risk-assessments/00000000-0000-0000-0000-000000000000").status_code == 403
    client.credentials()
    refresh = client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert refresh.status_code == 200
    assert client.post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json").status_code == 401
    rotated = refresh.json()["refresh"]
    assert client.post("/api/v1/auth/token/logout/", {"refresh": rotated}, format="json").status_code == 200
    assert client.post("/api/v1/auth/token/refresh/", {"refresh": rotated}, format="json").status_code == 401


@pytest.mark.django_db
def test_invalid_token_and_non_manager_are_rejected(django_user_model):
    django_user_model.objects.create_user("other", password="example-password-123")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer invalid")
    assert client.get("/api/v1/risk-rules").status_code == 401
    client.credentials()
    token = client.post(
        "/api/v1/auth/token/", {"username": "other", "password": "example-password-123"}, format="json"
    ).json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert client.get("/api/v1/risk-rules").status_code == 403


@pytest.mark.django_db
def test_payment_service_role_has_access_but_cannot_list_rules(django_user_model):
    user = django_user_model.objects.create_user("s3-service", password="example-password-123")
    user.groups.add(Group.objects.create(name="payment_service"))
    client = APIClient()
    token = client.post(
        "/api/v1/auth/token/", {"username": "s3-service", "password": "example-password-123"}, format="json"
    ).json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert client.get("/api/v1/risk-rules").status_code == 403
    assert client.get("/api/v1/risk-assessments/00000000-0000-0000-0000-000000000000").status_code == 404


@pytest.mark.django_db
def test_expired_and_wrong_audience_tokens_are_rejected(django_user_model):
    user = django_user_model.objects.create_user("jwt-check")
    user.groups.add(Group.objects.create(name="manager"))
    client = APIClient()
    expired = AccessToken.for_user(user)
    expired.set_exp(lifetime=timedelta(seconds=-1))
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired}")
    assert client.get("/api/v1/risk-rules").status_code == 401
    wrong_audience = AccessToken.for_user(user)
    wrong_audience["aud"] = "different-service"
    token = jwt.encode(wrong_audience.payload, settings.JWT_SIGNING_KEY, algorithm="HS256")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert client.get("/api/v1/risk-rules").status_code == 401
