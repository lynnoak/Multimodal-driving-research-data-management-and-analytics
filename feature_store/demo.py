"""Idempotent initialization restricted to a new, isolated synthetic database."""
from feature_store.config import DEMO_DATABASE
from feature_store.repository import FeatureRepository


def seed_demo(client):
    from app.services.demo import demo_records
    from app.schemas.features import FeatureResponse
    repo = FeatureRepository(client, database=DEMO_DATABASE)
    repo.ensure_indexes()
    inserted = 0
    for record in demo_records():
        record = FeatureResponse.model_validate(record).model_dump(by_alias=True)
        key = record.pop('_id')
        result = repo.collection.update_one({'_id': key}, {'$setOnInsert': record}, upsert=True)
        inserted += result.upserted_id is not None
    return inserted
