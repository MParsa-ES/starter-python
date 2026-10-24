from rest_framework.test import APIClient

from dashboard import selectors

URL = "/api/v1/risk-statistics"
RANGE = {"start": "2026-10-24T00:00:00Z", "end": "2026-10-25T00:00:00Z"}
REVERSED = {"start": "2026-10-25T00:00:00Z", "end": "2026-10-24T00:00:00Z"}


def test_valid_range_returns_statistics(monkeypatch):
    monkeypatch.setattr(
        selectors, "count_decisions_by_type", lambda start, end: {"APPROVE": 5, "REJECT": 1}
    )
    monkeypatch.setattr(selectors, "count_open_review_items", lambda: 2)

    response = APIClient().get(URL, RANGE)

    assert response.status_code == 200
    assert response.data["decisions"] == {"APPROVE": 5, "REVIEW": 0, "REJECT": 1}
    assert response.data["queue_size_now"] == 2


def test_reversed_range_returns_400_problem_details():
    response = APIClient().get(URL, REVERSED)

    assert response.status_code == 400
    assert response["Content-Type"].startswith("application/problem+json")
    assert response.data["code"] == "VALIDATION_ERROR"
    assert response.data["status"] == 400


def test_missing_parameters_return_400():
    response = APIClient().get(URL)

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"


def test_response_carries_the_correlation_header(monkeypatch):
    monkeypatch.setattr(selectors, "count_decisions_by_type", lambda start, end: {})
    monkeypatch.setattr(selectors, "count_open_review_items", lambda: 0)

    response = APIClient().get(URL, RANGE)

    assert response["X-Correlation-ID"]
