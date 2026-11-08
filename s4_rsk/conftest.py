import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-neighbor-contract", action="store_true", default=False,
        help="Run contract tests against the explicitly configured neighbour or stub.",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-neighbor-contract"):
        return
    skip = pytest.mark.skip(reason="Pass --run-neighbor-contract to contact a running neighbour or stub")
    for item in items:
        if item.get_closest_marker("contract"):
            item.add_marker(skip)
