from django.test import TestCase
from django.utils import timezone

from flights.models import LiveFlight, LiveFlightCloseReason, OperatorProfile, Pilot
from flights.utils.live_flight import (
    get_dashboard_live_flights,
    record_live_flight_event,
    reconcile_duplicate_active_flights,
)


class LiveFlightDedupTests(TestCase):
    def setUp(self):
        self.pilot = Pilot.objects.create(callname='Фелис', tg_id=6913473659)
        self.chat_id = -1003960872491

    def test_duplicate_start_message_is_idempotent(self):
        first = record_live_flight_event(
            action='start',
            telegram_user_id=self.pilot.tg_id,
            chat_id=self.chat_id,
            message_id=9001,
        )
        second = record_live_flight_event(
            action='start',
            telegram_user_id=self.pilot.tg_id,
            chat_id=self.chat_id,
            message_id=9001,
        )
        self.assertTrue(first['ok'])
        self.assertTrue(second['ok'])
        self.assertEqual(
            LiveFlight.objects.filter(message_id_start=9001).count(),
            1,
        )

    def test_reconcile_keeps_single_active_per_pilot(self):
        now = timezone.now()
        for message_id in range(9101, 9104):
            LiveFlight.objects.create(
                pilot=self.pilot,
                telegram_user_id=self.pilot.tg_id,
                chat_id=self.chat_id,
                started_at=now,
                message_id_start=message_id,
            )
        reconcile_duplicate_active_flights()
        self.assertEqual(
            LiveFlight.objects.filter(pilot=self.pilot, ended_at__isnull=True).count(),
            1,
        )
        self.assertEqual(
            LiveFlight.objects.filter(
                pilot=self.pilot,
                close_reason=LiveFlightCloseReason.NEW_START,
            ).count(),
            2,
        )

    def test_dashboard_hides_new_start_completed_rows(self):
        now = timezone.now()
        LiveFlight.objects.create(
            pilot=self.pilot,
            telegram_user_id=self.pilot.tg_id,
            chat_id=self.chat_id,
            started_at=now,
            ended_at=now,
            close_reason=LiveFlightCloseReason.NEW_START,
            message_id_start=9201,
        )
        real = LiveFlight.objects.create(
            pilot=self.pilot,
            telegram_user_id=self.pilot.tg_id,
            chat_id=self.chat_id,
            started_at=now,
            ended_at=now,
            close_reason=LiveFlightCloseReason.STOP,
            message_id_start=9202,
        )
        payload = get_dashboard_live_flights()
        completed_ids = {item['id'] for item in payload['completed']}
        self.assertIn(str(real.id), completed_ids)
        self.assertEqual(len([c for c in payload['completed'] if c['callname'] == 'Фелис']), 1)

    def test_start_stop_syncs_operator_duty(self):
        profile = OperatorProfile.objects.create(pilot=self.pilot)
        event_at = timezone.now()

        start = record_live_flight_event(
            action='start',
            telegram_user_id=self.pilot.tg_id,
            chat_id=self.chat_id,
            message_id=9301,
            event_at=event_at,
        )
        profile.refresh_from_db()
        self.assertTrue(start['ok'])
        self.assertEqual(profile.duty_started_at, event_at)

        stop = record_live_flight_event(
            action='stop',
            telegram_user_id=self.pilot.tg_id,
            chat_id=self.chat_id,
            message_id=9302,
            event_at=event_at,
        )
        profile.refresh_from_db()
        self.assertTrue(stop['ok'])
        self.assertIsNone(profile.duty_started_at)

    def test_timeout_clears_operator_duty(self):
        from datetime import timedelta

        profile = OperatorProfile.objects.create(pilot=self.pilot)
        started = timezone.now() - timedelta(hours=1)
        LiveFlight.objects.create(
            pilot=self.pilot,
            telegram_user_id=self.pilot.tg_id,
            chat_id=self.chat_id,
            started_at=started,
            message_id_start=9401,
        )
        profile.duty_started_at = started
        profile.save(update_fields=['duty_started_at', 'modified'])

        payload = get_dashboard_live_flights()
        profile.refresh_from_db()

        self.assertEqual(payload['active'], [])
        self.assertIsNone(profile.duty_started_at)
