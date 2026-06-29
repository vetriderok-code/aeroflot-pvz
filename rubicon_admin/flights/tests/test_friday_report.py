from datetime import date

from django.test import SimpleTestCase

from flights.models import FlightResultTypes
from flights.utils.friday_report import (
    DIRECTION_EAST_THRESHOLD,
    _build_summary,
    _is_combat_success_result,
    _is_provision_flight,
    _resolve_direction,
    _target_abbreviation,
    build_drone_docx_paragraphs,
    build_friday_report_docx_paragraphs,
    build_summary_docx_paragraphs,
    build_summary_lines,
    format_period_ru,
    friday_report_week_dates,
    parse_report_period,
    resolve_direction_key,
)


class FridayReportWeekDatesTests(SimpleTestCase):
    def test_current_week(self):
        monday, friday = friday_report_week_dates(
            week_offset=0,
            now=date(2025, 6, 4),
        )
        self.assertEqual(monday, date(2025, 6, 2))
        self.assertEqual(friday, date(2025, 6, 6))

    def test_parse_custom_period(self):
        start, end = parse_report_period(date_from='2026-05-25', date_to='2026-06-01')
        self.assertEqual(start, date(2026, 5, 25))
        self.assertEqual(end, date(2026, 6, 1))


class FridayReportDirectionTests(SimpleTestCase):
    def test_east_threshold(self):
        flight = type('F', (), {'direction': ''})()
        self.assertEqual(
            resolve_direction_key(north_meters=5_300_000, east_meters=DIRECTION_EAST_THRESHOLD, flight=flight),
            'dobropillia',
        )
        self.assertEqual(
            resolve_direction_key(north_meters=5_300_000, east_meters=DIRECTION_EAST_THRESHOLD - 1, flight=flight),
            'zaporizhzhia',
        )

    def test_kharkiv_by_north(self):
        flight = type('F', (), {'direction': ''})()
        self.assertEqual(
            resolve_direction_key(north_meters=5_400_000, east_meters=7_300_000, flight=flight),
            'kharkiv',
        )

    def test_explicit_direction(self):
        flight = type('F', (), {'direction': 'Северное'})()
        self.assertEqual(
            _resolve_direction(east_meters=7_000_000, flight=flight),
            'Северное',
        )


class FridayReportSummaryTests(SimpleTestCase):
    def test_summary_text_format(self):
        rows = [
            {
                'target': 'огневая позиция',
                'target_display': 'огневая позиция',
                'direction_key': 'zaporizhzhia',
                'is_provision': False,
                'provision_bucket': 'combined',
            },
            {
                'target': 'обеспечение',
                'target_display': 'обеспечение',
                'direction_key': 'dobropillia',
                'is_provision': True,
                'provision_bucket': 'combined',
            },
            {
                'target': 'бпла',
                'target_display': 'БпЛА',
                'direction_key': 'dobropillia',
                'is_provision': False,
                'provision_bucket': 'combined',
            },
        ]
        summary = _build_summary(rows, period_from=date(2026, 5, 25), period_to=date(2026, 6, 1))
        lines = build_summary_lines(summary)
        text = '\n'.join(lines)

        self.assertIn('В период с 25 мая по 1 июня', text)
        self.assertIn('на Запорожском ТН:', text)
        self.assertIn('огневая позиция – 01 ед.', text)
        self.assertNotIn('огневая позиция – 01 ед.;', text)
        self.assertIn('на Добропольском ТН:', text)
        self.assertIn('БпЛА – 01 ед.', text)
        self.assertNotIn('БпЛА – 01 ед.;', text)
        self.assertIn('союзные силы - 01 ед.', text)
        self.assertNotIn('свои и союзные силы', text)
        self.assertIn('ВСЕГО УНИЧТОЖЕНО: 2 цели.', text)
        self.assertEqual(format_period_ru(date(2026, 5, 25), date(2026, 6, 1)), 'с 25 мая по 1 июня')

    def test_docx_paragraphs_structure(self):
        rows = [
            {
                'target': 'огневая позиция',
                'target_display': 'огневая позиция',
                'direction_key': 'kharkiv',
                'is_provision': False,
                'provision_bucket': 'combined',
            },
        ]
        summary = _build_summary(rows, period_from=date(2026, 5, 25), period_to=date(2026, 6, 1))
        paragraphs = build_summary_docx_paragraphs(summary)
        self.assertGreaterEqual(len(paragraphs), 10)
        self.assertTrue(paragraphs[0].align, 'both')
        self.assertTrue(paragraphs[1].runs[0].bold)
        self.assertTrue(paragraphs[-1].runs[0].bold)
        self.assertIn('ВСЕГО УНИЧТОЖЕНО:', paragraphs[-1].runs[0].text)

    def test_target_abbreviations(self):
        self.assertEqual(_target_abbreviation('огневая позиция'), 'ОП')
        self.assertEqual(_target_abbreviation('инженерное сооружение'), 'ИС')
        self.assertEqual(_target_abbreviation('бпла'), 'БпЛА')

    def test_provision_flight_detection(self):
        obespechenie = type('F', (), {'target': 'Обеспечение', 'result_raw': 'успешно'})()
        combat = type('F', (), {'target': 'огневая позиция', 'result_raw': 'поражено'})()

        self.assertTrue(_is_provision_flight(obespechenie))
        self.assertFalse(_is_provision_flight(combat))

    def test_combat_success_result_filter(self):
        ok = type('F', (), {'result_raw': 'поражено', 'result': FlightResultTypes.DEFEATED})()
        dobiv = type('F', (), {'result_raw': 'добивание', 'result': FlightResultTypes.NOT_DEFEATED})()
        sjo = type('F', (), {'result_raw': 'успешно', 'result': FlightResultTypes.DEFEATED})()
        bad = type('F', (), {'result_raw': 'не успешно', 'result': FlightResultTypes.DEFEATED})()

        self.assertTrue(_is_combat_success_result(ok))
        self.assertFalse(_is_combat_success_result(dobiv))
        self.assertFalse(_is_combat_success_result(sjo))
        self.assertFalse(_is_combat_success_result(bad))

    def test_drone_docx_sections(self):
        rows = [
            {
                'target': 'огневая позиция',
                'target_display': 'огневая позиция',
                'direction_key': 'zaporizhzhia',
                'drone': '1-570 v.2',
                'coord_x': 5275256,
                'coord_y': 7278171,
                'is_provision': False,
            },
            {
                'target': 'обеспечение',
                'target_display': 'обеспечение',
                'direction_key': 'dobropillia',
                'drone': 'П-40-30',
                'coord_x': 5351127,
                'coord_y': 7371483,
                'is_provision': True,
                'provision_bucket': 'combined',
            },
        ]
        settlements = ['Червоное', 'Мирноград']
        paragraphs = build_drone_docx_paragraphs(
            rows,
            settlements,
            period_from=date(2026, 5, 25),
            period_to=date(2026, 6, 1),
        )
        text = '\n'.join(''.join(run.text for run in p.runs) for p in paragraphs)
        self.assertIn('ПРИМЕНЕНИЕ «1-570 v.2»:', text)
        self.assertIn('ПРИМЕНЕНИЕ «П-40-30»:', text)
        self.assertIn('ОП (X- 5275256; Y- 7278171) н.п. Червоное.', text)
        self.assertIn('доставлено 1 ед. груза.', text)
        self.assertIn('В период с 25.05.2026 по 01.06.2026 г.', text)

        full_doc = build_friday_report_docx_paragraphs(
            rows,
            settlements,
            period_from=date(2026, 5, 25),
            period_to=date(2026, 6, 1),
        )
        full_text = '\n'.join(''.join(run.text for run in p.runs) for p in full_doc)
        self.assertIn('ВСЕГО УНИЧТОЖЕНО:', full_text)
        self.assertIn('ПРИМЕНЕНИЕ «1-570 v.2»:', full_text)
