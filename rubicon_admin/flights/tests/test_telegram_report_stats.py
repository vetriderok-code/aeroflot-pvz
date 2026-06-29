from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, override_settings

from flights.utils.telegram_report_stats import (
    _dashboard_shift_period_bounds,
    is_report_defeated,
    is_report_not_defeated,
    parse_report_coordinates,
    parse_telegram_report_message,
)


class TelegramReportResultClassificationTests(SimpleTestCase):
    def test_porazheno(self):
        self.assertTrue(is_report_defeated('поражено'))
        self.assertTrue(is_report_defeated('Поражен'))
        self.assertFalse(is_report_not_defeated('поражено'))

    def test_not_defeated(self):
        self.assertTrue(is_report_not_defeated('не поражено'))
        self.assertTrue(is_report_not_defeated('Не  поражено'))
        self.assertTrue(is_report_not_defeated('непоражено'))
        self.assertFalse(is_report_defeated('не поражено'))
        self.assertFalse(is_report_defeated('не\u00a0поражено'))

    def test_unichtozheno(self):
        self.assertTrue(is_report_defeated('уничтожено'))

    def test_uspeh_not_defeated_kpi(self):
        self.assertFalse(is_report_defeated('успешно'))
        self.assertFalse(is_report_not_defeated('успешно'))


class TelegramReportParserTests(SimpleTestCase):
    def test_short_report(self):
        parsed = parse_telegram_report_message(
            '42 вылет\n31.05.2026\nпоражено',
            pilot_callsign='Alpha',
        )
        self.assertTrue(parsed['parse_ok'])
        self.assertEqual(parsed['flight_number'], 42)
        self.assertEqual(parsed['work_date'], '31.05.2026')
        self.assertEqual(parsed['result'], 'поражено')

    def test_number_only_first_line(self):
        parsed = parse_telegram_report_message('15')
        self.assertTrue(parsed['parse_ok'])
        self.assertEqual(parsed['flight_number'], 15)

    def test_video_style_caption(self):
        parsed = parse_telegram_report_message(
            '7 вылет\n31.05.2026\nне поражено',
            pilot_callsign='Test',
        )
        self.assertTrue(parsed['parse_ok'])
        self.assertEqual(parsed['flight_number'], 7)
        self.assertEqual(parsed['result'], 'не поражено')

    def test_report_with_coordinates(self):
        body = (
            '4 вылет\n06.06.2026\nпоражено\n'
            'X = 5289364  Y = 7283866\n'
            'Пилот: Костыль'
        )
        parsed = parse_telegram_report_message(body)
        self.assertTrue(parsed['parse_ok'])
        self.assertAlmostEqual(parsed['lat_wgs84'], 48.0, delta=1.5)
        self.assertGreater(parsed['lon_wgs84'], 34)

    def test_parse_report_coordinates_helper(self):
        coords = parse_report_coordinates('X = 5359504  Y = 7360000')
        self.assertIn('coordinates_sk42', coords)
        self.assertIsNotNone(coords.get('lat_wgs84'))

    def test_parse_td_report_coordinates_line(self):
        body = (
            '📊 ОТЧЕТ О ПОЛЕТЕ\n'
            'Вылет: 3\n'
            'Оператор: ставр\n'
            'Результат: поражено\n'
            'Координаты: 5278744 7278684\n'
        )
        parsed = parse_telegram_report_message(body)
        self.assertTrue(parsed['parse_ok'])
        self.assertEqual(parsed['flight_number'], 3)
        self.assertEqual(parsed['pilot_callsign'], 'ставр')
        self.assertAlmostEqual(parsed['lat_wgs84'], 47.5, delta=1.5)
        self.assertGreater(parsed['lon_wgs84'], 35)


class ShiftPeriodBoundsTests(SimpleTestCase):
    @override_settings(
        DASHBOARD_SHIFT_DAY_START_HOUR=6,
        DASHBOARD_SHIFT_NIGHT_START_HOUR=18,
    )
    def test_day_shift_window(self):
        tz = ZoneInfo('Europe/Moscow')
        now = datetime(2026, 5, 31, 12, 0, tzinfo=tz)
        start, end, kind, label = _dashboard_shift_period_bounds(now)
        self.assertEqual(kind, 'day')
        self.assertEqual(start.hour, 6)
        self.assertEqual(end.hour, 12)
        self.assertIn('06:00', label)

    @override_settings(
        DASHBOARD_SHIFT_DAY_START_HOUR=6,
        DASHBOARD_SHIFT_NIGHT_START_HOUR=18,
    )
    def test_night_shift_after_18(self):
        tz = ZoneInfo('Europe/Moscow')
        now = datetime(2026, 5, 31, 20, 0, tzinfo=tz)
        start, end, kind, _ = _dashboard_shift_period_bounds(now)
        self.assertEqual(kind, 'night')
        self.assertEqual(start.hour, 18)
        self.assertEqual(start.day, 31)

    @override_settings(
        DASHBOARD_SHIFT_DAY_START_HOUR=6,
        DASHBOARD_SHIFT_NIGHT_START_HOUR=18,
    )
    def test_night_shift_before_6(self):
        tz = ZoneInfo('Europe/Moscow')
        now = datetime(2026, 5, 31, 3, 0, tzinfo=tz)
        start, end, kind, _ = _dashboard_shift_period_bounds(now)
        self.assertEqual(kind, 'night')
        self.assertEqual(start.hour, 18)
        self.assertEqual(start.day, 30)


class CalendarDayBoundsTests(SimpleTestCase):
    @override_settings(
        DASHBOARD_SHIFT_DAY_START_HOUR=6,
        DASHBOARD_SHIFT_NIGHT_START_HOUR=18,
    )
    def test_operational_day_starts_at_6am_msk(self):
        from flights.utils.telegram_report_stats import _calendar_day_msk_period_bounds

        tz = ZoneInfo('Europe/Moscow')
        now = datetime(2026, 5, 31, 15, 30, tzinfo=tz)
        start, end = _calendar_day_msk_period_bounds(now)
        self.assertEqual(start.hour, 6)
        self.assertEqual(start.minute, 0)
        self.assertEqual(start.day, 31)
        self.assertEqual(end.hour, 15)
        self.assertEqual(end.minute, 30)

    def test_operational_day_before_6am_uses_previous_anchor(self):
        from flights.utils.telegram_report_stats import _calendar_day_msk_period_bounds

        tz = ZoneInfo('Europe/Moscow')
        now = datetime(2026, 5, 31, 3, 0, tzinfo=tz)
        start, end = _calendar_day_msk_period_bounds(now)
        self.assertEqual(start.hour, 6)
        self.assertEqual(start.day, 30)
        self.assertEqual(end.day, 31)
