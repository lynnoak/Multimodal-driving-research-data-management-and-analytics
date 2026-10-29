from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from fastapi.security import APIKeyHeader
from app.core.dependencies import repository
from app.schemas.features import (FeatureCreate, FeaturePatch, FeatureResponse, FeaturePage,
                                  Scenario, Patient, Label, StatsResponse)
from app.services.features import new_record, serialize

# Kong enforces this header. Declaring it also enables Swagger's Authorize UI.
api_key = APIKeyHeader(name='X-API-Key', auto_error=False)
router = APIRouter(prefix='/api/v1', dependencies=[Depends(api_key)])


@router.get('/demo/features', response_model=FeaturePage)
def synthetic_features():
    """A fixed fictional dataset for safe portfolio demonstrations; no DB access."""
    from app.services.demo import demo_records
    items = demo_records()
    return {'total': len(items), 'limit': len(items), 'offset': 0, 'items': items}


def page(repo, patient, scenario, label, limit, offset):
    total, records = repo.page(patient, scenario, label, limit, offset)
    return {'total': total, 'limit': limit, 'offset': offset,
            'items': [serialize(r) for r in records]}


@router.get('/features', response_model=FeaturePage)
def list_features(patient: Optional[Patient] = None, scenario: Optional[Scenario] = None,
                  label: Optional[Label] = None, limit: int = Query(50, ge=1, le=500),
                  offset: int = Query(0, ge=0), repo=Depends(repository)):
    return page(repo, patient, scenario, label, limit, offset)


@router.get('/features/export', response_class=Response)
def export_features(patient: Optional[Patient] = None, scenario: Optional[Scenario] = None,
                    label: Optional[Label] = None, repo=Depends(repository)):
    frame = repo.to_dataframe(patient, scenario, label)
    return Response(frame.to_csv(index=False), media_type='text/csv',
                    headers={'Content-Disposition': 'attachment; filename="scenario_features.csv"'})


@router.get('/features/{record_id}', response_model=FeatureResponse)
def get_feature(record_id: str, repo=Depends(repository)):
    record = repo.get(record_id)
    if record is None:
        raise HTTPException(404, 'Feature record not found')
    return serialize(record)


@router.post('/features', response_model=FeatureResponse, status_code=201)
def create_feature(payload: FeatureCreate, request: Request, repo=Depends(repository)):
    if request.app.state.mode == 'demo' and not payload.patient_id.startswith('P99-'):
        raise HTTPException(422, 'Demo accepts only fictional P99 subject codes')
    return serialize(repo.insert(new_record(payload)))


@router.patch('/features/{record_id}', response_model=FeatureResponse)
def patch_feature(record_id: str, payload: FeaturePatch, repo=Depends(repository)):
    record = repo.patch(record_id, features=payload.features, label=payload.label)
    if record is None:
        raise HTTPException(404, 'Feature record not found')
    return serialize(record)


@router.get('/patients/{patient_id}/features', response_model=FeaturePage)
def patient_features(patient_id: Patient, scenario: Optional[Scenario] = None,
                     label: Optional[Label] = None, limit: int = Query(50, ge=1, le=500),
                     offset: int = Query(0, ge=0), repo=Depends(repository)):
    return page(repo, patient_id, scenario, label, limit, offset)


@router.get('/scenarios/{scenario_type}/features', response_model=FeaturePage)
def scenario_features(scenario_type: Scenario, patient: Optional[Patient] = None,
                      label: Optional[Label] = None, limit: int = Query(50, ge=1, le=500),
                      offset: int = Query(0, ge=0), repo=Depends(repository)):
    return page(repo, patient, scenario_type, label, limit, offset)


@router.get('/stats', response_model=StatsResponse)
def statistics(include_labels: bool = True, repo=Depends(repository)):
    return repo.stats(include_labels)
