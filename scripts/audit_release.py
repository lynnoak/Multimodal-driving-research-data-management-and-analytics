"""Inspect the proposed public file set without staging, committing or reading datasets."""
from pathlib import Path
import json
import re
import subprocess


def candidates():
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            capture_output=True, check=True)
    return sorted(set(p for p in result.stdout.decode('utf-8').split('\0') if p))


def audit():
    files = candidates()
    findings = []
    for name in files:
        path = Path(name)
        if path.parts[0] in {'output', 'feature_store_output', 'tools', 'feature_extraction'} or name in {
            'feature_extract.py', 'compose.yaml', 'compose.debug.yaml'}:
            findings.append('Private workflow artifact present in proposed public file set')
        if path.suffix.lower() in {'.csv', '.json', '.xlsx', '.exe', '.zip', '.dump', '.pyc'}:
            findings.append(f'Forbidden artifact: {name}')
        if path.name.startswith('.env') and path.name != '.env.example':
            findings.append(f'Environment file: {name}')
        if path.is_symlink():
            findings.append(f'Symlink requires review: {name}')
        if path.stat().st_size > 2_000_000:
            findings.append(f'Large artifact requires review: {name}')
        if path.suffix.lower() in {'.py', '.md', '.txt', '.yaml', '.yml', '.sh', '.toml', '.ini', '.example'}:
            text = path.read_text(encoding='utf-8-sig')
            if re.search(r'[A-Za-z]:\\Users\\|/(?:home|Users)/[A-Za-z0-9._-]+/', text):
                findings.append(f'Personal filesystem path: {name}')
            if re.search(r'P0[0-9]-(?:FAKE-)?[0-9]+', text):
                findings.append(f'Non-demo participant marker: {name}')
            if re.search(r'[\u4e00-\u9fff]', text):
                findings.append(f'Non-English text requires review: {name}')
            if re.search(r'(?i)(?:password|api_key|token|secret)\s*=\s*[\'"][A-Za-z0-9_-]{32,}[\'"]', text):
                findings.append(f'Potential literal credential: {name}')
    report = {'files': files, 'file_count': len(files),
              'total_bytes': sum(Path(p).stat().st_size for p in files), 'findings': findings}
    print(json.dumps(report, indent=2))
    if findings:
        raise SystemExit(1)
    return report


if __name__ == '__main__':
    audit()
