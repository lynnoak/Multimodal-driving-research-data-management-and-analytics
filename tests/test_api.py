from copy import deepcopy
from io import StringIO
import os
from uuid import uuid4

from bson import ObjectId
from fastapi.testclient import TestClient
import mongomock
import pandas as pd
from pymongo.errors import ServerSelectionTimeoutError
import pytest

from app.main import create_app
from app.core.dependencies import repository
from app.services.features import new_record
from app.schemas.features import FeatureCreate
from feature_store.repository import FeatureRepository


def payload():
    return {'patient_id': 'P99-999', 'scenario': 'scenario_1', 'label': 'Health',
            'source_scenario_id': '123456789012345678901234', 'configuration_hash': 'a' * 64,
            'dataset': 'synthetic-test',
            'features': {'ECG_Rate_Mean': 71.25, 'SIM_Rea_cor_pos_5.0': 0.5,
                         'EEG_Alpha_AF7': None}}


@pytest.fixture
def api():
    mongo = mongomock.MongoClient(tz_aware=True)
    database = 'simulator_api_test_' + uuid4().hex
    repo = FeatureRepository(mongo, database)
    first = new_record(FeatureCreate(**payload()))
    second_payload = payload()
    second_payload.update(patient_id='P99-998', scenario='scenario_5', label='Disease')
    repo.insert(first)
    repo.insert(new_record(FeatureCreate(**second_payload)))
    application = create_app(mongo, database)
    with TestClient(application) as client:
        yield client, repo, first
    # Database is unique to this fixture and contains only synthetic records.
    repo.collection.delete_many({})
    mongo.close()


def test_health_page_filters_and_stats(api):
    client, repo, first = api
    assert client.get('/health').json() == {'status': 'ok'}
    response = client.get('/api/v1/features', params={'limit': 1, 'offset': 1})
    assert response.status_code == 200
    body = response.json()
    assert (body['total'], body['limit'], body['offset'], len(body['items'])) == (2, 1, 1, 1)
    for path in ['/api/v1/features?patient=P99-999&scenario=scenario_1&label=Health',
                 '/api/v1/patients/P99-999/features', '/api/v1/scenarios/scenario_1/features']:
        body = client.get(path).json()
        assert body['total'] == 1
        assert body['items'][0]['_id'] == first['_id']
    assert client.get('/api/v1/stats').json() == {'total': 2, 'scenarios': {'scenario_1': 1, 'scenario_5': 1},
                                               'labels': {'Health': 1, 'Disease': 1}}
    assert client.get('/api/v1/stats?include_labels=false').json()['labels'] is None


def test_lookup_export_and_openapi(api):
    client, repo, first = api
    response = client.get('/api/v1/features/' + first['_id'])
    assert response.status_code == 200
    assert response.json()['features']['ECG_Rate_Mean'] == 71.25
    assert response.json()['features']['EEG_Alpha_AF7'] is None
    assert client.get('/api/v1/features/missing').status_code == 404
    legacy = deepcopy(first)
    legacy['_id'] = ObjectId()
    repo.insert(legacy)
    assert client.get('/api/v1/features/' + str(legacy['_id'])).json()['_id'] == str(legacy['_id'])
    response = client.get('/api/v1/features/export?scenario=scenario_5')
    assert response.status_code == 200 and response.headers['content-type'].startswith('text/csv')
    frame = pd.read_csv(StringIO(response.text), float_precision='round_trip')
    assert len(frame) == 1
    assert frame.iloc[0]['SIM_Rea_cor_pos_5.0'] == 0.5
    assert frame.iloc[0]['ECG_Rate_Mean'] == 71.25
    assert client.get('/docs').status_code == 200
    schema = client.get('/openapi.json').json()
    assert schema['components']['securitySchemes']['APIKeyHeader']['name'] == 'X-API-Key'


def test_create_and_duplicate(api):
    client, repo, first = api
    body = payload()
    body['source_scenario_id'] = 'A' * 24
    response = client.post('/api/v1/features', json=body)
    assert response.status_code == 201
    result = response.json()
    assert len(result['_id']) == 64
    assert result['provenance']['kind'] == 'api'
    assert result['import_count'] == 1
    assert result['source_scenario_id'] == 'a' * 24
    body['source_scenario_id'] = 'a' * 24
    assert client.post('/api/v1/features', json=body).status_code == 409
    assert repo.collection.count_documents({}) == 3


@pytest.mark.parametrize('changes', [
    {'patient_id': 'Someone Smith'}, {'scenario': 'scenario_6'}, {'label': 'unknown'},
    {'features': {'ECG_Rate_Mean': '74'}}, {'features': {'ECG_Rate_Mean': True}},
    {'features': {'ECG_Rate_Mean': None}}, {'features': {'patient_name': 1}},
    {'features': {'ECG_Rate_Mean': 2**64}}, {'provenance': {'kind': 'forged'}},
    {'features': {'ECG_$field': 1}}, {'source_scenario_id': 'not-an-objectid'}])
def test_create_validation(api, changes):
    client, repo, first = api
    body = payload()
    body.update(changes)
    response = client.post('/api/v1/features', json=body)
    assert response.status_code == 422
    assert 'Someone Smith' not in response.text
    assert repo.collection.count_documents({}) == 2


@pytest.mark.parametrize('query', ['limit=0', 'limit=501', 'offset=-1', 'scenario=unknown', 'patient=John'])
def test_query_validation(api, query):
    assert api[0].get('/api/v1/features?' + query).status_code == 422


@pytest.mark.parametrize('body', [{}, {'label': None}, {'features': None}, {'features': {}},
                                  {'patient_id': 'P99-998'}, {'provenance': {}}, {'_id': 'x'},
                                  {'features': {'ECG_Rate_Mean': 'bad'}}])
def test_patch_validation(api, body):
    client, repo, first = api
    assert client.patch('/api/v1/features/' + first['_id'], json=body).status_code == 422



def test_database_error_handling(api):
    client, repo, first = api
    class Broken:
        def page(self, *args):
            raise ServerSelectionTimeoutError('sensitive internal database address/password')
    client.app.dependency_overrides[repository] = lambda: Broken()
    response = client.get('/api/v1/features')
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'database_unavailable'
    assert 'sensitive' not in response.text
    client.app.dependency_overrides.clear()
