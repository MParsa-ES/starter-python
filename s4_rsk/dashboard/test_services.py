from datetime import datetime, timezone

from dashboard import selectors, services

START = datetime(2026, 10, 24, tzinfo=timezone.utc)
END = datetime(2026, 10, 25, tzinfo=timezone.utc)


def fake_selectors(monkeypatch, decisions, queue=0):
    monkeypatch.setattr(selectors, "count_decisions_by_type", lambda start, end: decisions)
    monkeypatch.setattr(selectors, "count_open_review_items", lambda: queue)


def test_missing_decision_types_are_filled_with_zero(monkeypatch):
    fake_selectors(monkeypatch, {"APPROVE": 3})

    result = services.build_statistics(START, END)

    assert result["decisions"] == {"APPROVE": 3, "REVIEW": 0, "REJECT": 0}


def test_empty_range_gives_all_zeros(monkeypatch):
    fake_selectors(monkeypatch, {})

    result = services.build_statistics(START, START)

    assert result["decisions"] == {"APPROVE": 0, "REVIEW": 0, "REJECT": 0}


def test_queue_size_is_reported_separately_from_decisions(monkeypatch):
    fake_selectors(monkeypatch, {"REVIEW": 4}, queue=7)

    result = services.build_statistics(START, END)

    assert result["decisions"]["REVIEW"] == 4
    assert result["queue_size_now"] == 7


def test_range_is_passed_unchanged_to_the_selector(monkeypatch):
    received = {}

    def spy(start, end):
        received["range"] = (start, end)
        return {}

    monkeypatch.setattr(selectors, "count_decisions_by_type", spy)
    monkeypatch.setattr(selectors, "count_open_review_items", lambda: 0)

    result = services.build_statistics(START, END)

    assert received["range"] == (START, END)
    assert result["start"] == START
    assert result["end"] == END
