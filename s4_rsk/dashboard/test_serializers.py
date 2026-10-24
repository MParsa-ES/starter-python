import pytest

from dashboard.serializers import StatisticsQuerySerializer

DAY_START = "2026-10-24T00:00:00Z"
DAY_END = "2026-10-25T00:00:00Z"


def test_valid_range_is_accepted():
    serializer = StatisticsQuerySerializer(data={"start": DAY_START, "end": DAY_END})

    assert serializer.is_valid(), serializer.errors


def test_start_equal_to_end_is_an_empty_but_valid_range():
    serializer = StatisticsQuerySerializer(data={"start": DAY_START, "end": DAY_START})

    assert serializer.is_valid(), serializer.errors


def test_reversed_range_is_rejected():
    serializer = StatisticsQuerySerializer(data={"start": DAY_END, "end": DAY_START})

    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"start": DAY_START},
        {"end": DAY_END},
        {"start": "not-a-date", "end": DAY_END},
        {"start": DAY_START, "end": "2026-13-45T00:00:00Z"},
    ],
)
def test_missing_or_malformed_values_are_rejected(data):
    serializer = StatisticsQuerySerializer(data=data)

    assert not serializer.is_valid()


def test_parsed_values_are_timezone_aware():
    serializer = StatisticsQuerySerializer(data={"start": DAY_START, "end": DAY_END})
    serializer.is_valid(raise_exception=True)

    assert serializer.validated_data["start"].tzinfo is not None
    assert serializer.validated_data["end"].tzinfo is not None
