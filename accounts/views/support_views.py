from rest_framework import status, views, permissions
from rest_framework.response import Response


class UserSupportTicketListView(views.APIView):
    """
    User Support Portal:
    GET  /api/auth/support/ -> Retrieve all support/problem tickets submitted by the authenticated user.
    POST /api/auth/support/ -> Submit a new problem message or support inquiry to Super Admin.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from admin_panel.models import PlatformReport
        from admin_panel.serializers import PlatformReportSerializer
        tickets = PlatformReport.objects.filter(reporter=request.user).order_by('-created_at')
        return Response(PlatformReportSerializer(tickets, many=True).data)

    def post(self, request):
        from admin_panel.models import PlatformReport
        from admin_panel.serializers import PlatformReportSerializer

        reason = (request.data.get('reason') or '').strip()
        details = (request.data.get('details') or '').strip()
        report_type = (request.data.get('reportType') or request.data.get('report_type') or 'support').strip()
        target_model = (request.data.get('targetModel') or request.data.get('target_model') or 'Platform').strip()
        target_id = str(request.data.get('targetId') or request.data.get('target_id') or '').strip()

        if not reason:
            return Response({'reason': ['Please provide a subject line or summary of your problem.']}, status=status.HTTP_400_BAD_REQUEST)
        if not details:
            return Response({'details': ['Please describe the issue or message in detail.']}, status=status.HTTP_400_BAD_REQUEST)

        ticket = PlatformReport.objects.create(
            reporter=request.user,
            report_type=report_type,
            target_model=target_model,
            target_id=target_id,
            reason=reason,
            details=details,
            status='Pending'
        )
        return Response(PlatformReportSerializer(ticket).data, status=status.HTTP_201_CREATED)


class UserSupportTicketDetailView(views.APIView):
    """
    GET /api/auth/support/<int:pk>/ -> Retrieve specific support ticket for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        from admin_panel.models import PlatformReport
        from admin_panel.serializers import PlatformReportSerializer

        ticket = PlatformReport.objects.filter(pk=pk, reporter=request.user).first()
        if not ticket:
            return Response({'detail': 'Support ticket not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PlatformReportSerializer(ticket).data)
