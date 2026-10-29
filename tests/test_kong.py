"""Gateway verification against the isolated fictional Demo only."""
import os
import time
import httpx
import pytest
from dotenv import load_dotenv


@pytest.fixture(scope='module')
def gateway():
    if os.getenv('RUN_KONG_TESTS') != '1':
        pytest.skip('Set RUN_KONG_TESTS=1 with the Compose stack running')
    load_dotenv('.env.demo')
    with httpx.Client(base_url=os.getenv('KONG_TEST_URL', 'http://127.0.0.1:18000'), timeout=15) as client:
        # Allow independent reruns if a previous run exhausted the minute bucket.
        headers = {'X-API-Key': os.environ['DEMO_API_KEY']}
        response = client.get('/api/v1/stats', headers=headers)
        if response.status_code == 429:
            time.sleep(min(int(response.headers.get('Retry-After', '60')), 60))
        yield client, headers


def test_gateway_public_health_docs_and_auth(gateway):
    client, headers = gateway
    assert client.get('/health').status_code == 200
    assert client.get('/docs').status_code == 200
    assert client.get('/openapi.json').status_code == 200
    for path in ['/api/v1/features', '/api/v1/stats', '/api/v1/features/export', '/api/v1/demo/features',
                 '/api/v1/patients/P99-001/features', '/api/v1/scenarios/scenario_1/features']:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={'X-API-Key': 'invalid-key'}).status_code == 401
    assert client.get('/api/v1/features', params={'X-API-Key': headers['X-API-Key']}).status_code == 401


def test_gateway_routing_filters_and_export(gateway):
    client, headers = gateway
    response = client.get('/api/v1/features?limit=2', headers=headers)
    assert response.status_code == 200
    page = response.json()
    assert page['total'] == 60 and len(page['items']) == 2
    record = page['items'][0]
    assert client.get('/api/v1/features/' + record['_id'], headers=headers).json() == record
    response = client.get('/api/v1/scenarios/scenario_1/features?limit=1', headers=headers)
    assert response.status_code == 200 and response.json()['total'] == 12
    csv = client.get('/api/v1/features/export?scenario=scenario_1', headers=headers)
    assert csv.status_code == 200 and 'ECG_Rate_Mean' in csv.text
    assert client.get('/api/v1/stats', headers=headers).json()['total'] == 60


def test_gateway_rate_limit(gateway):
    client, headers = gateway
    threshold = int(os.getenv('DEMO_RATE_LIMIT_PER_MINUTE', '60'))
    statuses = []
    for _ in range(threshold + 1):
        response = client.get('/api/v1/stats', headers=headers)
        statuses.append(response.status_code)
        if response.status_code == 429:
            assert 'Retry-After' in response.headers
            break
    assert 429 in statuses
    assert all(code in (200, 429) for code in statuses)
    assert client.get('/health').status_code == 200
