import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import get_dashboard_summary

logger = logging.getLogger(__name__)


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.debug('Dashboard summary viewed by user=%s', request.user)
        return Response(get_dashboard_summary(request.user))
