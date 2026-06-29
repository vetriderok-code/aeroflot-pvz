from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from flights.utils.nearest_settlement import _cache_key, resolve_settlements_batch


class ResolveSettlementsBatchTests(SimpleTestCase):
    def tearDown(self):
        cache.clear()

    @patch('flights.utils.nearest_settlement.get_nearest_settlement_name')
    def test_deduplicates_coordinates(self, mock_geocode):
        mock_geocode.side_effect = lambda lat, lon, allow_nominatim=True: f'place-{lat}-{lon}'

        points = [
            {'lat': 48.1, 'lon': 37.1},
            {'lat': 48.1, 'lon': 37.1},
            {'lat': 47.9, 'lon': 36.8},
        ]
        names = resolve_settlements_batch(points)

        self.assertEqual(names, ['place-48.1-37.1', 'place-48.1-37.1', 'place-47.9-36.8'])
        self.assertEqual(mock_geocode.call_count, 2)

    @patch('flights.utils.nearest_settlement.get_nearest_settlement_name')
    def test_uses_cache_for_repeated_batch(self, mock_geocode):
        mock_geocode.return_value = 'Червоное'
        lat, lon = 48.3937, 37.1678
        cache.set(_cache_key(lat, lon), 'Червоное', 3600)

        names = resolve_settlements_batch([{'lat': lat, 'lon': lon}] * 3)

        self.assertEqual(names, ['Червоное', 'Червоное', 'Червоное'])
        mock_geocode.assert_not_called()

    @patch('flights.utils.nearest_settlement._fetch_yandex_with_key')
    def test_tries_extra_yandex_key_first(self, mock_fetch):
        from django.test import override_settings
        from flights.utils.nearest_settlement import _fetch_yandex

        mock_fetch.side_effect = lambda lat, lon, key: 'Новый' if key.endswith('5089') else ''

        with override_settings(
            YANDEX_API_KEY='old-key',
            YANDEX_API_KEY_EXTRA='8c1cfc61-abf8-401e-97ae-e6e9c1215089',
        ):
            self.assertEqual(_fetch_yandex(48.39, 37.16), 'Новый')
        self.assertEqual(mock_fetch.call_count, 1)
        self.assertTrue(mock_fetch.call_args[0][2].endswith('5089'))

    @patch('flights.utils.nearest_settlement._fetch_photon')
    @patch('flights.utils.nearest_settlement._fetch_yandex')
    def test_uses_photon_when_yandex_empty(self, mock_yandex, mock_photon):
        mock_yandex.return_value = ''
        mock_photon.return_value = 'Білицьке'
        from flights.utils.nearest_settlement import get_nearest_settlement_name

        cache.clear()
        name = get_nearest_settlement_name(48.3937, 37.1678, allow_nominatim=False)
        self.assertEqual(name, 'Білицьке')
        mock_photon.assert_called_once()

    @patch('flights.utils.nearest_settlement.get_nearest_settlement_name')
    def test_skips_cached_dash_for_relookup(self, mock_geocode):
        lat, lon = 48.3937, 37.1678
        cache.set(_cache_key(lat, lon), '—', 3600)
        mock_geocode.return_value = 'Червоное'

        names = resolve_settlements_batch([{'lat': lat, 'lon': lon}])

        self.assertEqual(names, ['Червоное'])
        mock_geocode.assert_called_once()
