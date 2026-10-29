"""Inspectable calculations; missingness does not establish clinical validity."""
import hashlib
import hmac
import math
import numbers
import pandas as pd

GROUPS = {'ECG': 'Cardiac', 'EDA': 'Electrodermal', 'EEG': 'Brain activity',
          'EYE': 'Eye tracking', 'HEAD': 'Head movement', 'SIM': 'Driving simulator',
          'PRE': 'Questionnaire'}
METADATA = ['_id', 'id', 'id_anonymat', 'id_scenario', 'label']


def feature_columns(frame):
    return [c for c in frame.columns if c.split('_', 1)[0] in GROUPS]


def flatten(items):
    return pd.DataFrame([{'_id': r['_id'], 'id': r.get('source_scenario_id'),
                          'id_anonymat': r['patient_id'], 'id_scenario': r['scenario'],
                          'label': r['label'], **r['features']} for r in items],
                        ) if items else pd.DataFrame(columns=METADATA)


def filter_frame(frame, patient=None, scenario=None, label=None):
    result = frame
    for col, value in [('id_anonymat', patient), ('id_scenario', scenario), ('label', label)]:
        if value is not None:
            result = result[result[col] == value]
    return result.copy()


def summary(frame):
    return {'total': len(frame),
            'scenarios': frame.id_scenario.value_counts().sort_index().to_dict(),
            'labels': frame.label.value_counts().sort_index().to_dict()}


def subject_alias(value, secret):
    token = hmac.new(secret.encode(), str(value).encode(), hashlib.sha256).hexdigest()[:12]
    return 'Subject ' + token.upper()


def public_frame(frame, secret):
    """Never send source IDs or original participant codes to the browser."""
    result = frame.drop(columns=['_id', 'id', 'id_anonymat'], errors='ignore').copy()
    if 'id_anonymat' in frame:
        result.insert(0, 'Subject', frame.id_anonymat.map(lambda p: subject_alias(p, secret)))
    return result.rename(columns={'id_scenario': 'Scenario', 'label': 'Label'})


def quality(frame):
    columns = feature_columns(frame)
    values = frame[columns]
    valid = values.map(lambda v: isinstance(v, numbers.Real) and not isinstance(v, bool)
                       and math.isfinite(v))
    missing = values.isna()
    invalid = ~valid & ~missing
    n = len(frame)
    cells = n * len(columns)
    features = pd.DataFrame({'Feature': columns,
                            'Observed': valid.sum().to_numpy(dtype=int),
                            'Missing': missing.sum().to_numpy(dtype=int),
                            'Invalid': invalid.sum().to_numpy(dtype=int)})
    features['Missing (%)'] = features.Missing * 100 / n if n else 0.0
    modalities = []
    for prefix, name in GROUPS.items():
        fields = [c for c in columns if c.startswith(prefix + '_')]
        # Scenario 5 is physiological-only under the extraction contract.
        eligible = frame.id_scenario != 'scenario_5' if prefix == 'SIM' else pd.Series(True, index=frame.index)
        denominator = int(eligible.sum())
        available = int(valid.loc[eligible, fields].any(axis=1).sum()) if fields else 0
        modalities.append({'Modality': prefix, 'Description': name, 'Feature fields': len(fields),
                           'Eligible records': denominator, 'Available records': available,
                           'Availability (%)': 100 * available / denominator if denominator else None})
    return {'records': n, 'feature_fields': len(columns), 'cells': cells,
            'observed_cells': int(valid.sum().sum()), 'missing_cells': int(missing.sum().sum()),
            'invalid_cells': int(invalid.sum().sum()),
            'missing_percent': 100 * missing.sum().sum() / cells if cells else None,
            'all_missing_fields': int(missing.all().sum()) if n else 0,
            'records_without_values': int((~valid.any(axis=1)).sum()),
            'duplicate_record_ids': int(frame['_id'].duplicated().sum()) if '_id' in frame else 0,
            'features': features, 'modalities': pd.DataFrame(modalities)}


def dataset_export(frame, groups, include_subject=False, secret=''):
    columns = [c for c in feature_columns(frame) if c.split('_', 1)[0] in groups]
    result = frame[['id_scenario', 'label'] + columns].copy()
    if include_subject:
        result.insert(0, 'subject_key', frame.id_anonymat.map(lambda p: subject_alias(p, secret)))
    return result
