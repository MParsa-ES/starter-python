from urllib.parse import parse_qs, urlparse
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response


class LabBankCursorPagination(CursorPagination):
    """
    GEN-09: Lists are paginated with limit (max 200) and cursor,
    and the response includes next_cursor.
    """

    page_size = 50
    page_size_query_param = "limit"
    max_page_size = 200
    cursor_query_param = "cursor"
    ordering = "-created_at"

    def get_paginated_response(self, data):
        next_link = self.get_next_link()
        next_cursor = None
        if next_link:
            parsed = urlparse(next_link)
            cursor_values = parse_qs(parsed.query).get(self.cursor_query_param)
            if cursor_values:
                next_cursor = cursor_values[0]

        return Response(
            {
                "items": data,
                "next_cursor": next_cursor,
            }
        )