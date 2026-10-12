from rest_framework.pagination import PageNumberPagination

from core.errors import APIError


class ContractPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        for name in ("page", "page_size"):
            raw = request.query_params.get(name)
            if raw is not None and (not raw.isdecimal() or int(raw) < 1):
                raise APIError("VALIDATION_ERROR", f"{name} must be a positive integer.")
        return super().paginate_queryset(queryset, request, view)


def paginated(request, queryset, serializer):
    pagination = ContractPagination()
    page = pagination.paginate_queryset(queryset, request)
    return pagination.get_paginated_response(serializer(page, many=True).data)
