from datetime import time

from django.test import SimpleTestCase, override_settings

from flights.utils.raschety_pilot_import import (
    _parse_duty_range,
    _parse_shift,
    read_raschety_rows,
)


class RaschetyPilotImportTests(SimpleTestCase):
    def test_parse_shift(self):
        self.assertEqual(_parse_shift('День'), 'day')
        self.assertEqual(_parse_shift('Ночь'), 'night')
        self.assertIsNone(_parse_shift(''))

    def test_parse_comm_links(self):
        from flights.utils.raschety_pilot_import import parse_comm_links_from_cell
        self.assertEqual(parse_comm_links_from_cell('Оптика'), ['optics'])
        self.assertEqual(parse_comm_links_from_cell('Оптика+СКС'), ['optics', 'sks'])
        self.assertEqual(parse_comm_links_from_cell('Старлинк'), ['starlink'])
        self.assertEqual(parse_comm_links_from_cell('Радиостанция Старлинк'), ['starlink'])
        self.assertEqual(parse_comm_links_from_cell('БШПД'), ['bshpd'])

    def test_parse_duty_range(self):
        self.assertEqual(_parse_duty_range('08:00-20:00'), (time(8, 0), time(20, 0)))
        self.assertEqual(_parse_duty_range('08.00–20.00'), (time(8, 0), time(20, 0)))
        self.assertEqual(_parse_duty_range(''), (None, None))

    @override_settings(DASHBOARD_SHIFT_DAY_START_HOUR=6, DASHBOARD_SHIFT_NIGHT_START_HOUR=18)
    def test_read_raschety_rows_from_share(self):
        path = '/Volumes/data/Обмен/Расчёты.xlsx'
        try:
            rows = read_raschety_rows(path)
        except FileNotFoundError:
            self.skipTest('файл Расчёты.xlsx недоступен')
        except ValueError as exc:
            if 'не найден' in str(exc):
                self.skipTest(str(exc))
            raise
        self.assertGreaterEqual(len(rows), 30)
        felis = next((r for r in rows if r.callname == 'Фелис'), None)
        self.assertIsNotNone(felis)
        self.assertEqual(felis.engineer_callname, 'Гримм')
        self.assertEqual(felis.placement_zone, 'day')
        self.assertEqual(felis.group_name, '1 ИГ (ТД)')
        self.assertEqual(felis.location_name, 'ОЛИМП')
        self.assertEqual(felis.settlement, 'ДИМИТРОВ (5470)')
        self.assertEqual(felis.comm_link_raw, 'Оптика')
