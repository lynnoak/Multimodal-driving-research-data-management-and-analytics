from datetime import datetime, timezone
from feature_store.repository import digest


def serialize(record):
    result = dict(record)
    result['_id'] = str(result['_id'])
    if result.get('source_scenario_id') is not None:
        result['source_scenario_id'] = str(result['source_scenario_id'])
    return result


def new_record(payload):
    dataset = digest(payload.dataset)
    identity = [payload.patient_id, payload.scenario, payload.source_scenario_id] if payload.source_scenario_id else [
        payload.patient_id, payload.scenario, dataset, payload.configuration_hash]
    now = datetime.now(timezone.utc)
    return {'_id': digest(identity), 'patient_id': payload.patient_id, 'scenario': payload.scenario,
            'label': payload.label, 'source_scenario_id': payload.source_scenario_id,
            'configuration_hash': payload.configuration_hash, 'features': payload.features,
            'provenance': {'kind': 'api', 'dataset': dataset, 'raw_database': None,
                           'feature_files': {}, 'questionnaire_sha256': None, 'labels_sha256': None,
                           'record_sha256': digest([identity, payload.features, payload.label]), 'schema_version': 1},
            'imported_at': now, 'last_imported_at': now, 'import_count': 1}
