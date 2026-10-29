import argparse
from pathlib import Path
from feature_store.config import mongo_client
from feature_store.repository import FeatureRepository, LABELS


def main():
    parser = argparse.ArgumentParser(description='Query features and export a flat Pandas CSV')
    parser.add_argument('--patient')
    parser.add_argument('--scenario', choices=[f'scenario_{n}' for n in range(1, 6)])
    parser.add_argument('--label', choices=sorted(LABELS))
    parser.add_argument('--csv', type=Path)
    args = parser.parse_args()
    with mongo_client() as client:
        frame = FeatureRepository(client).to_dataframe(args.patient, args.scenario, args.label)
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.csv, index=False)
    print(f'{len(frame)} records; {len(frame.columns)} columns')
    print(frame[['id_anonymat', 'id_scenario', 'label']].head().to_string(index=False))


if __name__ == '__main__':
    main()
