from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class AdminPanelPagination(PageNumberPagination):
    """
    Standard pagination for Super Admin API endpoints.
    Allows dynamic page sizing via ?page_size=25.
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'totalPages': self.page.paginator.num_pages,
            'currentPage': self.page.number,
            'pageSize': self.get_page_size(self.request),
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })
