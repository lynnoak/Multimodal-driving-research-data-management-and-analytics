"""Create separate local Demo credentials without opening the private .env."""
from pathlib import Path
import os
import secrets


def setup(path=Path('.env.demo')):
    path = Path(path)
    if path.exists():
        print('Demo environment already exists; it was not changed.')
        return False
    text = ('DEMO_MONGO_USER=simulator_demo_admin\n'
            f'DEMO_MONGO_PASSWORD={secrets.token_urlsafe(32)}\n'
            f'DEMO_API_KEY={secrets.token_urlsafe(32)}\n'
            'DEMO_RATE_LIMIT_PER_MINUTE=60\nDEMO_API_PORT=18000\nDEMO_DASHBOARD_PORT=18501\n')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as file:
        file.write(text)
    print('Created ignored .env.demo with new Demo-only credentials. No secrets printed.')
    return True


if __name__ == '__main__':
    setup()
