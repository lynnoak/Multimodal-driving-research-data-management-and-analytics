import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import MongoClient

DEMO_DATABASE = 'driving_features_demo'


def app_mode():
    mode = os.getenv('APP_MODE', 'demo')
    if mode not in {'demo', 'live'}:
        raise ValueError('APP_MODE must be demo or live')
    return mode


# Never auto-discover the private environment file in public Demo mode.
load_dotenv(Path(__file__).resolve().parents[1] / ('.env' if app_mode() == 'live' else '.env.demo'))


def mongo_client():
    if app_mode() == 'demo':
        if os.getenv('FEATURE_DATABASE', DEMO_DATABASE) != DEMO_DATABASE:
            raise ValueError('Demo requires its dedicated synthetic database')
        user, password = os.getenv('DEMO_MONGO_USER'), os.getenv('DEMO_MONGO_PASSWORD')
        if not user or not password:
            raise ValueError('Demo MongoDB credentials are not configured')
        # The public Demo is container-only. Ignore private URIs/host overrides.
        return MongoClient(f'mongodb://{quote_plus(user)}:{quote_plus(password)}@mongodb:27017/?authSource=admin',
                           serverSelectionTimeoutMS=3000, tz_aware=True)
    uri = os.getenv("MONGODB_URI")
    if not uri:
        user = os.getenv("MONGO_INITDB_ROOT_USERNAME")
        password = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
        if not user or not password:
            raise ValueError("Set MONGODB_URI or MongoDB credentials in .env")
        uri = (f"mongodb://{quote_plus(user)}:{quote_plus(password)}@"
               f"{os.getenv('MONGO_HOST', '127.0.0.1')}:{os.getenv('MONGO_PORT', '27017')}/?authSource=admin")
    return MongoClient(uri, serverSelectionTimeoutMS=3000, tz_aware=True)
