from io import StringIO
import json
import math
import os

from fastapi.testclient import TestClient
import httpx
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
import streamlit as st

from app.main import create_app
from app.services.demo import demo_records
from dashboard.client import FeatureClient, DashboardError
from dashboard.data import quality, flatten, public_frame, dataset_export, summary


def test_demo_api_needs_no_database():
    with TestClient(create_app(client=object())) as client:
        response = client.get('/api/v1/demo/features')
        assert response.status_code == 200
        body = response.json()
        assert body['total'] == len(body['items']) == 60
        assert {r['provenance']['kind'] for r in body['items']} == {'synthetic_demo'}
        assert all(r['_id'].startswith('synthetic-') for r in body['items'])


def test_quality_denominators_invalid_and_structural_missing():
    frame = pd.DataFrame([
        {'_id': 'a', 'id_scenario': 'scenario_1', 'ECG_Rate_Mean': 70, 'SIM_Reaction': 0.5, 'EEG_Alpha_AF7': None},
        {'_id': 'b', 'id_scenario': 'scenario_5', 'ECG_Rate_Mean': None, 'SIM_Reaction': None, 'EEG_Alpha_AF7': None},
        {'_id': 'b', 'id_scenario': 'scenario_1', 'ECG_Rate_Mean': math.inf, 'SIM_Reaction': 'bad', 'EEG_Alpha_AF7': None},
    ])
    report = quality(frame)
    assert (report['records'], report['feature_fields'], report['cells']) == (3, 3, 9)
    assert (report['observed_cells'], report['missing_cells'], report['invalid_cells']) == (2, 5, 2)
    assert report['missing_percent'] == pytest.approx(100 * 5 / 9)
    assert report['all_missing_fields'] == 1
    assert report['duplicate_record_ids'] == 1
    assert report['records_without_values'] == 2
    simulator = report['modalities'].set_index('Modality').loc['SIM']
    assert simulator['Eligible records'] == 2 and simulator['Available records'] == 1
    assert simulator['Availability (%)'] == 50
    empty = quality(frame.iloc[:0])
    assert empty['missing_percent'] is None and empty['all_missing_fields'] == 0
    assert empty['modalities']['Availability (%)'].isna().all()


def test_export_selection_privacy_and_values():
    original = flatten(demo_records())
    frame = original[(original.id_scenario == 'scenario_1') & (original.label == 'Health')]
    exported = dataset_export(frame, ['ECG'], include_subject=True, secret='test-secret')
    assert len(exported) == 4
    assert set(exported.columns) == {'id_scenario', 'label', 'subject_key', 'ECG_Rate_Mean', 'ECG_HRV_SDNN'}
    assert not any(p in exported.to_csv(index=False) for p in original.id_anonymat)
    assert not any(p in str(public_frame(original, 'test-secret')) for p in original.id_anonymat)
    parsed = pd.read_csv(StringIO(exported.to_csv(index=False)), float_precision='round_trip')
    assert parsed.ECG_Rate_Mean.tolist() == frame.ECG_Rate_Mean.tolist()
    assert parsed.ECG_HRV_SDNN.isna().tolist() == frame.ECG_HRV_SDNN.isna().tolist()
    assert summary(original)['total'] == 60


def test_client_only_uses_get_and_server_header():
    requests = []
    # Datetimes in demo records require JSON serialization just as the API does.
    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=json.dumps({'items': demo_records()}, default=str))
    client = FeatureClient(base_url='http://kong:8000', api_key='server-secret', mode='demo',
                           transport=httpx.MockTransport(handler))
    assert client.stats()['total'] == 60
    total, frame = client.page(scenario='scenario_1', limit=2, offset=2)
    assert total == 12 and len(frame) == 2
    assert len(requests) == 1  # Reuses its synthetic snapshot.
    assert requests[0].method == 'GET' and requests[0].headers['X-API-Key'] == 'server-secret'
    assert 'server-secret' not in str(requests[0].url)


@pytest.mark.parametrize('code', [401, 429, 503])
def test_client_errors_do_not_leak_upstream_body(code):
    client = FeatureClient(api_key='private-api-key', transport=httpx.MockTransport(
        lambda request: httpx.Response(code, text='private-api-key participant name')))
    with pytest.raises(DashboardError) as exc:
        client.stats()
    assert 'private-api-key' not in str(exc.value) and 'participant name' not in str(exc.value)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv('DASHBOARD_MODE', 'demo')
    monkeypatch.setenv('DASHBOARD_ALIAS_SECRET', 'ui-test-alias-key')
    monkeypatch.setenv('APTICONDUITE_API_KEY', 'server-secret')
    monkeypatch.setattr(FeatureClient, 'get', lambda *args, **kwargs: {'items': demo_records()})
    st.cache_data.clear()
    st.cache_resource.clear()
    result = AppTest.from_file('dashboard/streamlit_app.py', default_timeout=20).run()
    yield result
    st.cache_data.clear()
    st.cache_resource.clear()


def test_all_four_dashboard_pages(app):
    assert not app.exception and not app.error
    assert app.metric[0].value == '60'
    for page in ['Feature Explorer', 'Data Quality', 'Dataset Export']:
        app.radio[0].set_value(page).run()
        assert not app.exception and not app.error
        assert any(title.value == page for title in app.title)
        for table in app.dataframe:
            text = table.value.to_csv(index=False)
            assert 'P99-' not in text and 'server-secret' not in text


def test_explorer_filters_pagination_and_empty(app):
    app.radio[0].set_value('Feature Explorer').run()
    app.selectbox[3].select(10).run()
    app.number_input[0].set_value(2).run()
    assert len(app.dataframe[0].value) == 10
    app.selectbox[1].select('scenario_5').run()
    assert app.number_input[0].value == 1
    assert set(app.dataframe[0].value.Scenario) == {'scenario_5'}
    app.selectbox[2].select('Health').run()
    assert set(app.dataframe[0].value.Label) == {'Health'}


def test_quality_filters_and_export_groups(app):
    app.radio[0].set_value('Data Quality').run()
    app.selectbox[1].select('scenario_5').run()
    assert app.metric[0].value == '12'
    modalities = app.dataframe[0].value.set_index('Modality')
    assert modalities.loc['SIM', 'Eligible records'] == 0
    app.radio[0].set_value('Dataset Export').run()
    app.multiselect[0].set_value(['ECG']).run()
    assert all(c in ['id_scenario', 'label'] or c.startswith('ECG_') for c in app.dataframe[0].value.columns)
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any('Select a feature group' in x.value for x in app.info)


@pytest.mark.integration
def test_dashboard_reads_live_and_synthetic_through_kong():
    if os.getenv('RUN_DASHBOARD_TESTS') != '1':
        pytest.skip('Set RUN_DASHBOARD_TESTS=1 with Compose running')
    live = FeatureClient(mode='live')
    assert live.stats()['total'] == 60
    total, page = live.page(scenario='scenario_1', limit=2)
    assert total == 12 and len(page) == 2
    frame = live.dataset(scenario='scenario_5')
    assert len(frame) == 12
    report = quality(frame)
    assert report['records'] == 12
    assert report['invalid_cells'] == 0
    assert len(FeatureClient(mode='demo').dataset()) == 60
