from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Shared pagination for list endpoints via `?page=` and `?page_size=`."""
    page_size_query_param = 'page_size'
    max_page_size = 100
