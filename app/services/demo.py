"""Deterministic fictional observations, never loaded from or written to MongoDB."""
from datetime import datetime, timezone
import math


def demo_records():
    records = []
    for scenario in range(1, 6):
        for observation in range(12):
            index = (scenario - 1) * 12 + observation
            features = {
                'ECG_Rate_Mean': round(65 + 10 * math.sin(index / 7), 4),
                'ECG_HRV_SDNN': None if index % 9 == 0 else round(40 + index / 3, 4),
                'EDA_Tonic_SD': round(0.2 + (index % 8) / 20, 4),
                'EEG_Alpha_AF7': None if index % 7 == 0 else round(0.0001 * (1 + index % 6), 7),
                'EYE_Blink_rate': round(8 + index % 13, 4),
                'HEAD_eulerX': round(math.sin(index) / 4, 6),
                'SIM_Reaction': None if scenario == 5 else round(0.3 + index % 8 / 20, 4),
                'SIM_Rea_cor_pos_5.0': None if scenario != 1 else round(0.4 + observation / 40, 4),
                'PRE_interface': 1 + observation % 3,
                'PRE_driving_frequency_level': observation % 5,
            }
            records.append({'_id': f'synthetic-{index:04d}', 'patient_id': f'P99-{observation // 2 + 1:03d}',
                            'scenario': f'scenario_{scenario}',
                            'label': ['Health', 'Left_Loss', 'Right_Loss'][observation % 3],
                            'source_scenario_id': None, 'configuration_hash': '0' * 64,
                            'features': features,
                            'provenance': {'kind': 'synthetic_demo', 'dataset': 'fictional-portfolio-demo',
                                           'record_sha256': '0' * 64, 'schema_version': 1},
                            'imported_at': datetime(2026, 1, 1, tzinfo=timezone.utc),
                            'last_imported_at': datetime(2026, 1, 1, tzinfo=timezone.utc), 'import_count': 0})
    return records
