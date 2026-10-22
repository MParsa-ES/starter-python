import contextvars
import logging
from uuid6 import uuid7

# Context variable to hold correlation_id across the request lifecycle
_correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_correlation_id() -> str:
    """Retrieve the current request's X-Correlation-ID for logs and outbound HTTP calls."""
    cid = _correlation_id_ctx.get()
    if not cid:
        cid = str(uuid7())
        _correlation_id_ctx.set(cid)
    return cid


class CorrelationIdMiddleware:
    """
    GEN-08: Reads X-Correlation-ID from incoming request headers (or generates a UUIDv7),
    attaches it to request.correlation_id, and returns it in the response header.
    """

    HEADER_NAME = "HTTP_X_CORRELATION_ID"
    RESPONSE_HEADER = "X-Correlation-ID"

    def init(self, get_response):
        self.get_response = get_response

    def call(self, request):
        incoming_cid = request.META.get(self.HEADER_NAME)
        correlation_id = incoming_cid.strip() if incoming_cid else str(uuid7())

        token = _correlation_id_ctx.set(correlation_id)
        request.correlation_id = correlation_id

        try:
            response = self.get_response(request)
            response[self.RESPONSE_HEADER] = correlation_id
            return response
        finally:
            _correlation_id_ctx.reset(token)


class CorrelationIdLogFilter(logging.Filter):
    """
    GEN-11: Injects correlation_id and service name into every structured JSON log record.
    """

    def filter(self, record):
        record.correlation_id = _correlation_id_ctx.get() or None
        record.service = "s4-rsk"
        return True