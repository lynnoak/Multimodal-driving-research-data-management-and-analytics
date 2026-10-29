"""Essential synthetic-only isolation checks, with optional real Demo HTTP CRUD."""
import importlib
import json
import os
from pathlib import Path
import subprocess
from io import StringIO

import dotenv
import httpx
import mongomock
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from feature_store.config import DEMO_DATABASE
from feature_store.demo import seed_demo
from feature_store.repository import FeatureRepository


def test_demo_seed_is_isolated_idempotent_and_fictional():
    class IsolatedClient(mongomock.MongoClient):
        def __getitem__(self, name):
            assert name == DEMO_DATABASE, 'Non-demo database access attempted'
            return super().__getitem__(name)
    client = IsolatedClient(tz_aware=True)
    assert seed_demo(client) == 60
    repo = FeatureRepository(client, database=DEMO_DATABASE)
    original = repo.find()
    assert seed_demo(client) == 0 and repo.find() == original
    assert all(r['patient_id'].startswith('P99-') and r['provenance']['kind'] == 'synthetic_demo' for r in original)
    with TestClient(create_app(client, DEMO_DATABASE)) as api:
        assert api.get('/api/v1/stats').json()['total'] == 60
        frame = pd.read_csv(StringIO(api.get('/api/v1/features/export').text))
        assert frame.id_anonymat.str.startswith('P99-').all()
        assert len(frame) == 60
        assert api.get('/api/v1/features/not-a-demo-id').status_code == 404


def test_demo_ignores_private_environment_and_rejects_private_database(monkeypatch):
    import feature_store.config as config
    calls = []
    monkeypatch.setenv('APP_MODE', 'demo')
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda path, *args, **kwargs: calls.append(Path(path).name))
    importlib.reload(config)
    assert calls == ['.env.demo']
    monkeypatch.setenv('DEMO_MONGO_USER', 'fictional_user')
    monkeypatch.setenv('DEMO_MONGO_PASSWORD', 'fictional_password')
    monkeypatch.setenv('MONGODB_URI', 'mongodb://must-not-use:27017')
    monkeypatch.setenv('MONGO_HOST', 'must-not-use')
    monkeypatch.setenv('FEATURE_DATABASE', DEMO_DATABASE)
    captured = []
    monkeypatch.setattr(config, 'MongoClient', lambda uri, **kwargs: captured.append(uri))
    config.mongo_client()
    assert len(captured) == 1 and '@mongodb:27017/' in captured[0] and 'must-not-use' not in captured[0]
    monkeypatch.setenv('FEATURE_DATABASE', 'forbidden_database')
    with pytest.raises(ValueError, match='dedicated'):
        config.mongo_client()
    assert len(captured) == 1
    with pytest.raises(ValueError, match='non-demo'):
        with TestClient(create_app()):
            pass


def test_demo_setup_never_opens_private_env(tmp_path, monkeypatch):
    from scripts.setup_demo import setup
    monkeypatch.chdir(tmp_path)
    Path('.env').write_text('PRIVATE_SENTINEL=untouched', encoding='utf-8')
    assert setup() is True
    before = Path('.env.demo').read_bytes()
    assert setup() is False and before == Path('.env.demo').read_bytes()
    assert Path('.env').read_text() == 'PRIVATE_SENTINEL=untouched'


@pytest.mark.integration
def test_real_demo_crud_and_export():
    if os.getenv('RUN_DEMO_TESTS') != '1':
        pytest.skip('Set RUN_DEMO_TESTS=1 with compose.demo.yaml running')
    dotenv.load_dotenv('.env.demo')
    record_id = None
    command = ['docker', 'compose', '--env-file', '.env.demo', '-f', 'compose.demo.yaml', '-p', 'driving-simulator-demo']
    result = subprocess.run(command + ['config', '--format', 'json'], capture_output=True,
                            encoding='utf-8', check=True, timeout=30)
    config = json.loads(result.stdout)  # Never print rendered credential values.
    assert config['name'] == 'driving-simulator-demo'
    assert not config['services']['mongodb'].get('ports')
    assert not config['services']['fastapi'].get('ports')
    assert config['networks']['database']['internal'] is True
    assert set(config['volumes']) == {'synthetic_mongodb_data'}
    assert config['volumes']['synthetic_mongodb_data']['name'] == 'driving-simulator-demo_synthetic_mongodb_data'
    assert config['services']['fastapi']['environment']['FEATURE_DATABASE'] == DEMO_DATABASE
    assert config['services']['fastapi']['environment']['APP_MODE'] == 'demo'
    for name, service in config['services'].items():
        assert all(v['type'] == 'volume' and v['source'] == 'synthetic_mongodb_data'
                   for v in service.get('volumes', [])), name
    assert config['services']['streamlit']['environment']['DASHBOARD_BACKEND'] == 'store'
    with httpx.Client(base_url='http://127.0.0.1:18000', timeout=15,
                      headers={'X-API-Key': os.environ['DEMO_API_KEY']}) as api:
        assert api.get('/health').status_code == 200
        assert api.get('/api/v1/stats').json()['total'] == 60
        exported = pd.read_csv(StringIO(api.get('/api/v1/features/export').text))
        assert len(exported) == 60 and exported.id_anonymat.str.startswith('P99-').all()
        assert exported['_id'].str.startswith('synthetic-').all()
        payload = {'patient_id': 'P99-999', 'scenario': 'scenario_1', 'label': 'Health',
                   'source_scenario_id': 'f' * 24, 'configuration_hash': 'b' * 64,
                   'dataset': 'fictional-integration-test', 'features': {'ECG_Rate_Mean': 71.25, 'SIM_Rea_cor_pos_5.0': 0.5}}
        rejected = dict(payload, patient_id='P98-999')
        assert api.post('/api/v1/features', json=rejected).status_code == 422
        try:
            response = api.post('/api/v1/features', json=payload)
            assert response.status_code == 201
            created = response.json()
            record_id = created['_id']
            assert api.post('/api/v1/features', json=payload).status_code == 409
            response = api.patch('/api/v1/features/' + record_id, json={
                'label': 'Left_Loss', 'features': {'SIM_Rea_cor_pos_5.0': 0.75}})
            assert response.status_code == 200
            updated = response.json()
            assert updated['features'] == {'ECG_Rate_Mean': 71.25, 'SIM_Rea_cor_pos_5.0': 0.75}
            assert updated['provenance'] == created['provenance']
            assert api.get('/api/v1/features/' + record_id).json() == updated
        finally:
            if record_id:
                # Only this fictional test record in the dedicated Demo is removed.
                code = ("from feature_store.config import mongo_client,DEMO_DATABASE; "
                        "assert DEMO_DATABASE=='driving_features_demo'; "
                        "c=mongo_client(); "
                        f"r=c[DEMO_DATABASE].scenario_features.delete_one({{'_id':'{record_id}', 'patient_id':'P99-999', 'provenance.kind':'api'}}); "
                        "assert r.deleted_count==1; c.close()")
                subprocess.run(command + ['exec', '-T', 'fastapi', 'python', '-c', code], check=True,
                               capture_output=True, timeout=30)
        assert api.get('/api/v1/stats').json()['total'] == 60
