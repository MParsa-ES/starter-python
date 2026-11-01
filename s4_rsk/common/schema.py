from drf_spectacular.utils import OpenApiParameter, OpenApiTypes

CORRELATION_HEADERS = [
    OpenApiParameter(
        name="X-Correlation-ID",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.HEADER,
        description="Optional request trace identifier; generated when absent.",
    ),
    OpenApiParameter(
        name="X-Correlation-ID",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.HEADER,
        response=True,
        required=True,
        description="Trace identifier for this response and its logs.",
    ),
]
