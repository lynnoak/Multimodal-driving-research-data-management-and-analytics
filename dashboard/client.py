"""Server-side GET-only Kong client; errors never echo credentials or payloads."""
from io import StringIO
import os
import httpx
import pandas as pd
from dashboard.data import flatten, filter_frame, summary


class DashboardError(Exception):
    pass


class FeatureClient:
    def __init__(self, base_url=None, api_key=None, mode=None, transport=None):
        self.base_url = base_url or os.getenv('DASHBOARD_API_URL', 'http://127.0.0.1:18000')
        self.key = api_key or os.getenv('GATEWAY_API_KEY') or os.getenv('DEMO_API_KEY') or os.getenv('APTICONDUITE_API_KEY', '')
        self.mode = mode or os.getenv('DASHBOARD_MODE', 'demo')
        if self.mode not in {'demo', 'live'}:
            raise DashboardError('DASHBOARD_MODE must be demo or live.')
        self.transport = transport
        self._demo = None
        self.fixture = self.mode == 'demo' and os.getenv('DASHBOARD_BACKEND', 'fixture') == 'fixture'

    def get(self, path, params=None, csv=False):
        if not self.key:
            raise DashboardError('The dashboard API credential is not configured on the server.')
        try:
            with httpx.Client(base_url=self.base_url, timeout=20, transport=self.transport,
                              follow_redirects=False) as client:
                response = client.get(path, params=params, headers={'X-API-Key': self.key})
            if response.status_code == 429:
                raise DashboardError('The API request limit was reached. Wait one minute, then refresh.')
            if response.status_code in (401, 403):
                raise DashboardError('The server API credential was rejected. Check the dashboard configuration.')
            response.raise_for_status()
            return response.text if csv else response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DashboardError('The feature service is unavailable. Please try again shortly.') from None

    def demo(self):
        if self._demo is None:
            self._demo = flatten(self.get('/api/v1/demo/features')['items'])
        return self._demo.copy()

    def stats(self):
        return summary(self.demo()) if self.fixture else self.get('/api/v1/stats')

    def dataset(self, patient=None, scenario=None, label=None):
        if self.fixture:
            return filter_frame(self.demo(), patient, scenario, label)
        text = self.get('/api/v1/features/export', params=self.filters(patient, scenario, label), csv=True)
        return pd.read_csv(StringIO(text), dtype={'_id': str, 'id': str, 'id_anonymat': str},
                           float_precision='round_trip')

    @staticmethod
    def filters(patient, scenario, label):
        return {k: v for k, v in [('patient', patient), ('scenario', scenario), ('label', label)] if v is not None}

    def page(self, patient=None, scenario=None, label=None, limit=25, offset=0):
        if self.fixture:
            frame = self.dataset(patient, scenario, label)
            return len(frame), frame.iloc[offset:offset + limit].copy()
        result = self.get('/api/v1/features', params={**self.filters(patient, scenario, label),
                                                     'limit': limit, 'offset': offset})
        return result['total'], flatten(result['items'])
