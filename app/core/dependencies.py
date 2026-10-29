from fastapi import Request
from feature_store.repository import FeatureRepository


def repository(request: Request):
    return FeatureRepository(request.app.state.mongo_client,
                             database=request.app.state.database)
