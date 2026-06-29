from django.test import SimpleTestCase

from flights.utils.telegram_report_ingest import (
    _normalize_start_stop_command,
    extract_message_text,
)


class ExtractMessageTextTests(SimpleTestCase):
    def test_caption_only(self):
        self.assertEqual(
            extract_message_text(caption='3 вылет\nпоражено'),
            '3 вылет\nпоражено',
        )

    def test_text_preferred_over_caption(self):
        self.assertEqual(
            extract_message_text(text='Старт', caption='ignored'),
            'Старт',
        )


class StartStopCommandTests(SimpleTestCase):
    def test_normalize_case_insensitive(self):
        self.assertEqual(_normalize_start_stop_command('старт'), 'Старт')
        self.assertEqual(_normalize_start_stop_command('СТАРТ'), 'Старт')
        self.assertEqual(_normalize_start_stop_command('  Стоп  '), 'Стоп')
        self.assertIsNone(_normalize_start_stop_command('стартовый'))
