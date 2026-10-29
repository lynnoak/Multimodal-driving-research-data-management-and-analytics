"""Validated BSON-safe scenario records with deterministic upserts."""
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import os

import numpy as np
import pandas as pd
from pymongo import ASCENDING
from bson import ObjectId

DATABASE = 'apticonduite_features' if os.getenv('APP_MODE') == 'live' else 'driving_features_demo'
COLLECTION = "scenario_features"
LABELS = {'Health', 'Disease', 'Fake', 'Right_Loss', 'Left_Loss'}
METADATA = {"id", "id_test", "id_patient", "id_scenario", "id_anonymat", "label"}
PREFIXES = ("ECG_", "EDA_", "EEG_", "EYE_", "HEAD_", "SIM_", "PRE_")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode('utf-8')).hexdigest()


def source_key(patient, scenario, original, config_hash):
    return digest([patient, scenario, original, config_hash])


def numeric(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        return value
    if not isinstance(value, (int, float)):
        raise ValueError(f"Non-numeric feature value of type {type(value).__name__}")
    if not math.isfinite(value):
        return None
    if isinstance(value, int) and not -(2**63) <= value < 2**63:
        raise ValueError("Integer feature exceeds BSON int64")
    return value


def prepare_records(frame, provenance):
    if frame.empty or not frame.columns.is_unique:
        raise ValueError("Dataset must be nonempty with unique columns")
    if not METADATA.issubset(frame.columns):
        raise ValueError("Missing metadata columns")
    columns = [c for c in frame.columns if c not in METADATA]
    if not columns or any(not c.startswith(PREFIXES) or '\x00' in c for c in columns):
        raise ValueError("Only known numerical feature column families are allowed")
    records = []
    seen = set()
    # Do not persist arbitrary provenance dictionaries, paths, or names.
    dataset = str(provenance.get('dataset', 'unknown'))
    safe_dataset = dataset if re.fullmatch(r'\d{4}-\d\d-\d\d_\d\d_\d\d_\d\d', dataset) else digest(dataset)
    for row in frame.to_dict('records'):
        patient = row['id_anonymat']
        if not isinstance(patient, str) or not re.fullmatch(r'P\d{2}-(?:FAKE-)?\d+', patient):
            raise ValueError("Expected pseudonymous participant code, not a name")
        scenario = row['id_scenario']
        if scenario not in {f'scenario_{n}' for n in range(1, 6)}:
            raise ValueError("Invalid scenario metadata")
        label = row['label']
        if label not in LABELS:
            raise ValueError("Invalid or missing label")
        original = row['id']
        original = None if pd.isna(original) or not str(original).strip() else str(original).strip()
        # Known IDs remain strings; absent IDs remain absent. Config hashes avoid
        # retaining free text that might contain identifying information.
        config_hash = digest(str(row['id_test']))
        identity = [patient, scenario, original] if original else [patient, scenario, safe_dataset, config_hash]
        record_id = digest(identity)
        if record_id in seen:
            raise ValueError("Ambiguous or duplicate source identity in dataset")
        seen.add(record_id)
        features = {c: numeric(row[c]) for c in columns}
        if all(v is None for v in features.values()):
            raise ValueError("Record has no numerical feature values")
        record = {'_id': record_id, 'patient_id': patient, 'scenario': scenario,
                  'label': label, 'source_scenario_id': original,
                  'configuration_hash': config_hash, 'features': features,
                  'provenance': {'kind': provenance['kind'], 'dataset': safe_dataset,
                                 'raw_database': provenance.get('raw_database'),
                                 'feature_files': provenance.get('source_records', {}).get(
                                     source_key(patient, scenario, original, config_hash), {}),
                                 'questionnaire_sha256': provenance.get('questionnaire_sha256'),
                                 'labels_sha256': provenance.get('labels_sha256'),
                                 'record_sha256': digest([identity, features, label]),
                                 'schema_version': 1}}
        records.append(record)
    return records


class FeatureRepository:
    def __init__(self, client, database=DATABASE):
        self.collection = client[database][COLLECTION]

    def ensure_indexes(self):
        self.collection.create_index([('patient_id', ASCENDING), ('scenario', ASCENDING)])
        self.collection.create_index([('scenario', ASCENDING), ('label', ASCENDING)])
        self.collection.create_index('label')

    def import_frame(self, frame, provenance):
        records = prepare_records(frame, provenance)  # Validate entire batch before writes.
        self.ensure_indexes()
        now = datetime.now(timezone.utc)
        inserted = 0
        for record in records:
            key = record.pop('_id')
            result = self.collection.update_one({'_id': key},
                {'$set': {**record, 'last_imported_at': now},
                 '$setOnInsert': {'imported_at': now}, '$inc': {'import_count': 1}}, upsert=True)
            inserted += result.upserted_id is not None
        return {'processed': len(records), 'inserted': inserted,
                'updated': len(records) - inserted}

    def verify_frame(self, frame, provenance):
        """Verify every imported metadata field and feature value, including nulls."""
        expected = prepare_records(frame, provenance)
        actual = {r['_id']: r for r in self.collection.find({'_id': {'$in': [r['_id'] for r in expected]}})}
        for record in expected:
            stored = actual.get(record['_id'])
            if stored is None or any(stored.get(k) != v for k, v in record.items()):
                raise RuntimeError(f"Feature verification failed for {record['_id']}")
        return len(expected)

    def find(self, patient=None, scenario=None, label=None):
        query = {k: v for k, v in [('patient_id', patient), ('scenario', scenario), ('label', label)] if v is not None}
        return list(self.collection.find(query).sort('_id', ASCENDING))

    @staticmethod
    def filters(patient=None, scenario=None, label=None):
        return {k: v for k, v in [('patient_id', patient), ('scenario', scenario), ('label', label)] if v is not None}

    @staticmethod
    def record_filter(record_id):
        # 64-character deterministic strings remain strings. A legacy 24-char
        # ID can be stored as a literal string or a genuine BSON ObjectId.
        ids = [record_id]
        if ObjectId.is_valid(record_id):
            ids.append(ObjectId(record_id))
        return {'_id': {'$in': ids}}

    def page(self, patient=None, scenario=None, label=None, limit=50, offset=0):
        query = self.filters(patient, scenario, label)
        total = self.collection.count_documents(query)
        items = list(self.collection.find(query).sort('_id', ASCENDING).skip(offset).limit(limit))
        return total, items

    def get(self, record_id):
        return self.collection.find_one(self.record_filter(record_id))

    def insert(self, record):
        self.collection.insert_one(record)
        return record

    def patch(self, record_id, features=None, label=None):
        from pymongo import ReturnDocument
        changes = {'updated_at': datetime.now(timezone.utc)}
        if label is not None:
            changes['label'] = label
        # A literal object keeps dotted feature names intact; merge atomically
        # so concurrent patches to different feature keys do not lose updates.
        if features is not None:
            changes['features'] = {'$mergeObjects': ['$features', {'$literal': features}]}
        return self.collection.find_one_and_update(self.record_filter(record_id),
                    [{'$set': changes}], return_document=ReturnDocument.AFTER)

    def stats(self, include_labels=True):
        scenarios = {r['_id']: r['count'] for r in self.collection.aggregate([
            {'$group': {'_id': '$scenario', 'count': {'$sum': 1}}}])}
        labels = {r['_id']: r['count'] for r in self.collection.aggregate([
            {'$group': {'_id': '$label', 'count': {'$sum': 1}}}])} if include_labels else None
        return {'total': sum(scenarios.values()), 'scenarios': scenarios, 'labels': labels}

    def to_dataframe(self, patient=None, scenario=None, label=None):
        records = self.find(patient, scenario, label)
        rows = [{'_id': r['_id'], 'id': r['source_scenario_id'],
                 'id_anonymat': r['patient_id'], 'id_scenario': r['scenario'],
                 'label': r['label'], **r['features']} for r in records]
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=['_id', 'id', 'id_anonymat', 'id_scenario', 'label'])
