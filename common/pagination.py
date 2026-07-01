from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Shared pagination for all list endpoints: `?page=`/`?page_size=` per IMPLEMENTATION_PLAN.md §5."""
    page_size_query_param = 'page_size'
    max_page_size = 100
