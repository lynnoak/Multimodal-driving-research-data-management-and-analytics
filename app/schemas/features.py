from datetime import datetime
import math
import re
from typing import Annotated, Dict, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, field_validator, model_validator
from feature_store.repository import PREFIXES

Patient = Annotated[str, Field(pattern=r'^P\d{2}-(?:FAKE-)?\d+$', max_length=64)]
Scenario = Literal['scenario_1', 'scenario_2', 'scenario_3', 'scenario_4', 'scenario_5']
Label = Literal['Health', 'Disease', 'Fake', 'Right_Loss', 'Left_Loss']
Number = Optional[Union[StrictInt, StrictFloat]]


def validate_features(features):
    if not features or len(features) > 1000:
        raise ValueError('Provide 1 to 1000 numerical feature fields')
    for key, value in features.items():
        if not key.startswith(PREFIXES) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', key):
            raise ValueError('Unsupported feature name')
        if value is not None:
            if isinstance(value, int) and not -(2**63) <= value < 2**63:
                raise ValueError('Integer exceeds BSON int64')
            if isinstance(value, bool) or not math.isfinite(value):
                raise ValueError('Feature values must be finite numbers or null')
    return features


class FeatureCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    patient_id: Patient
    scenario: Scenario
    label: Label
    source_scenario_id: Optional[Annotated[str, Field(pattern=r'^[0-9a-fA-F]{24}$')]] = None
    # Only the hash is accepted; names/free-text configuration are not stored.
    configuration_hash: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    dataset: Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')]
    features: Dict[str, Number]

    _features = field_validator('features')(validate_features)

    @field_validator('source_scenario_id')
    @classmethod
    def canonical_source_id(cls, value):
        return value.lower() if value is not None else None

    @model_validator(mode='after')
    def has_values(self):
        if all(v is None for v in self.features.values()):
            raise ValueError('At least one numerical value is required')
        return self


class FeaturePatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: Optional[Label] = None
    features: Optional[Dict[str, Number]] = None

    @field_validator('features')
    @classmethod
    def valid_features(cls, value):
        if value is None:
            raise ValueError('features cannot be null')
        return validate_features(value)

    @model_validator(mode='after')
    def nonempty(self):
        if not self.model_fields_set or ('label' in self.model_fields_set and self.label is None):
            raise ValueError('Provide a non-null label or feature updates')
        return self


class Provenance(BaseModel):
    kind: str
    dataset: str
    raw_database: Optional[str] = None
    feature_files: Dict[str, str] = Field(default_factory=dict)
    questionnaire_sha256: Optional[str] = None
    labels_sha256: Optional[str] = None
    record_sha256: str
    schema_version: int


class FeatureResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(alias='_id')
    patient_id: Patient
    scenario: Scenario
    label: Label
    source_scenario_id: Optional[str] = None
    configuration_hash: str
    features: Dict[str, Number]
    provenance: Provenance
    imported_at: datetime
    last_imported_at: datetime
    import_count: int
    updated_at: Optional[datetime] = None


class FeaturePage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[FeatureResponse]


class StatsResponse(BaseModel):
    total: int
    scenarios: Dict[str, int]
    labels: Optional[Dict[str, int]] = None


class HealthResponse(BaseModel):
    status: Literal['ok']


class ErrorResponse(BaseModel):
    error: Dict[str, object]
