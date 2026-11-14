"""Check real HTTP responses against an OpenAPI 3.1 contract file.

The service is contract-first (ADR-002): ``openapi/s4_rsk.yaml`` is the agreement,
and the code must conform to it. ``assert_response_matches`` verifies that

1. the status code is documented for the operation (exact code or ``4XX``/``5XX``),
2. the ``Content-Type`` is one the contract lists for that status,
3. the JSON body satisfies the documented schema, and
4. every response header the contract declares is present.

It works with Django/DRF test responses and with ``httpx`` responses, so the same
helper validates our own API (provider tests) and a neighbour's API (consumer
contract tests).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[2]
PROVIDER_SPEC = REPO_ROOT / "openapi" / "s4_rsk.yaml"
NEIGHBOR_SPEC = REPO_ROOT / "openapi" / "neighbors" / "s2_ldg.yaml"


class ContractViolation(AssertionError):
    """The observed response is not allowed by the contract."""


@lru_cache(maxsize=None)
def load_spec(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _resolve(spec: dict, node: dict) -> dict:
    """Follow a local ``$ref`` such as ``#/components/responses/Forbidden``."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node:
        pointer = node["$ref"]
        if not pointer.startswith("#/"):
            raise ContractViolation(f"Only local $ref values are supported: {pointer}")
        target = spec
        for part in pointer[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        node = target
        seen += 1
        if seen > 20:
            raise ContractViolation(f"$ref loop at {pointer}")
    return node


def operation(spec: dict, path_template: str, method: str) -> dict:
    try:
        return spec["paths"][path_template][method.lower()]
    except KeyError as exc:
        raise ContractViolation(f"{method.upper()} {path_template} is not in the contract") from exc


def documented_statuses(spec: dict, path_template: str, method: str) -> list[str]:
    return sorted(operation(spec, path_template, method)["responses"])


def contract_example(spec: dict, path_template: str, method: str, status: str = "200") -> dict | list | None:
    """Return the ``example`` the contract gives for a response (used to build stubs)."""
    response = _resolve(spec, operation(spec, path_template, method)["responses"][status])
    media = next(iter(response.get("content", {}).values()), {})
    return media.get("example")


def _schema_validator(spec: dict, schema: dict) -> Draft202012Validator:
    # The whole document is embedded so that "#/components/..." references resolve.
    root = {"components": spec.get("components", {}), **schema}
    return Draft202012Validator(root, format_checker=FormatChecker())


def _header(response, name: str):
    headers = getattr(response, "headers", None)
    return headers.get(name) if headers is not None else None


def assert_response_matches(response, *, path_template: str, method: str, spec_path=PROVIDER_SPEC) -> None:
    spec = load_spec(spec_path)
    responses = operation(spec, path_template, method)["responses"]
    status = str(response.status_code)
    key = status if status in responses else f"{status[0]}XX" if f"{status[0]}XX" in responses else None
    if key is None:
        raise ContractViolation(
            f"{method.upper()} {path_template} returned {status}, but the contract documents only {sorted(responses)}"
        )
    declared = _resolve(spec, responses[key])

    content = declared.get("content") or {}
    if content:
        content_type = (_header(response, "Content-Type") or "").split(";")[0].strip().lower()
        media = content.get(content_type)
        if media is None:
            raise ContractViolation(
                f"{method.upper()} {path_template} {status}: Content-Type {content_type!r} "
                f"is not among {sorted(content)}"
            )
        if "schema" in media:
            errors = sorted(
                _schema_validator(spec, media["schema"]).iter_errors(response.json()),
                key=lambda error: tuple(str(part) for part in error.path),
            )
            if errors:
                lines = "; ".join(f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors[:5])
                raise ContractViolation(f"{method.upper()} {path_template} {status} body violates the schema: {lines}")

    for header_name in declared.get("headers", {}):
        if _header(response, header_name) is None:
            raise ContractViolation(f"{method.upper()} {path_template} {status}: header {header_name} is missing")


def assert_payload_matches(schema_name: str, payload, *, spec_path=PROVIDER_SPEC) -> None:
    """Check a request payload against ``components.schemas.<schema_name>``."""
    spec = load_spec(spec_path)
    validator = _schema_validator(spec, {"$ref": f"#/components/schemas/{schema_name}"})
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        raise ContractViolation(f"Payload violates {schema_name}: {errors[0].message}")
