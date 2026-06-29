from django.utils.dateparse import parse_datetime
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from flights.models import OperatorLocation, OperatorPlacementZone, OperatorProfile
from flights.utils.operator_dashboard import (
    comm_link_choices_payload,
    comm_link_labels,
    get_operator_dashboard_payload,
    get_position_history,
    normalize_comm_links,
    update_operator_location,
)


class OperatorDashboardAPIView(APIView):
    """Дашборд размещения операторов (день / ночь / отрыв)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = get_operator_dashboard_payload()
        payload['comm_link_choices'] = comm_link_choices_payload()
        payload['can_edit_comm'] = bool(
            request.user.is_staff or request.user.is_superuser
        )
        return Response(payload)


class OperatorPositionAPIView(APIView):
    """Перемещение оператора между расположениями (только staff)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'detail': 'Недостаточно прав.'}, status=403)

        profile_id = request.data.get('profile_id')
        location_id = request.data.get('location_id')
        if not profile_id or not location_id:
            return Response({'detail': 'profile_id и location_id обязательны.'}, status=400)

        try:
            profile = OperatorProfile.objects.select_related('pilot').get(pk=profile_id)
        except OperatorProfile.DoesNotExist:
            return Response({'detail': 'Оператор не найден.'}, status=404)

        try:
            location = OperatorLocation.objects.get(pk=location_id, is_active=True)
        except OperatorLocation.DoesNotExist:
            return Response({'detail': 'Расположение не найдено.'}, status=404)

        placement_zone = request.data.get('placement_zone')
        if placement_zone and placement_zone not in OperatorPlacementZone.values:
            return Response({'detail': 'Некорректная зона размещения.'}, status=400)

        detachment_destination = (
            request.data.get('detachment_destination')
            or request.data.get('comment')
            or ''
        ).strip()
        moving_to_detachment = (
            placement_zone == OperatorPlacementZone.DETACHMENT
            and profile.placement_zone != OperatorPlacementZone.DETACHMENT
        )
        if moving_to_detachment and not detachment_destination:
            return Response({'detail': 'Укажите, куда перемещаем.'}, status=400)

        duty_started_at = None
        raw_duty = request.data.get('duty_started_at')
        if raw_duty:
            duty_started_at = parse_datetime(raw_duty)

        try:
            profile = update_operator_location(
                profile=profile,
                location=location,
                placement_zone=placement_zone,
                duty_started_at=duty_started_at,
                comment=detachment_destination,
                detachment_destination=detachment_destination,
                recorded_by=request.user,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({
            'ok': True,
            'profile_id': str(profile.id),
            'location_id': str(profile.location_id) if profile.location_id else None,
            'location_label': profile.location_label,
            'placement_zone': profile.placement_zone,
            'notes': profile.notes or '',
        })


class OperatorLocationCommLinkAPIView(APIView):
    """Тип связи для расположения (только staff)."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, location_id):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'detail': 'Недостаточно прав.'}, status=403)

        try:
            location = OperatorLocation.objects.get(pk=location_id, is_active=True)
        except OperatorLocation.DoesNotExist:
            return Response({'detail': 'Расположение не найдено.'}, status=404)

        raw_links = request.data.get('comm_links')
        if raw_links is None and 'comm_link' in request.data:
            raw_links = [request.data.get('comm_link')]
        comm_links = normalize_comm_links(raw_links or [])

        location.comm_links = comm_links
        location.save(update_fields=['comm_links', 'modified'])

        return Response({
            'ok': True,
            'location_id': str(location.id),
            'comm_links': location.comm_links,
            'comm_link_labels': comm_link_labels(location.comm_links),
        })


class OperatorPositionHistoryAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, profile_id):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({'detail': 'Недостаточно прав.'}, status=403)
        limit = min(int(request.query_params.get('limit', 100)), 500)
        return Response({'history': get_position_history(profile_id, limit=limit)})
