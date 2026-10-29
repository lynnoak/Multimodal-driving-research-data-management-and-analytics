from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError, DuplicateKeyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.api.v1.routes import router
from app.schemas.features import HealthResponse, ErrorResponse
from feature_store.config import mongo_client, app_mode, DEMO_DATABASE


def error(status, code, message, details=None):
    body = {'code': code, 'message': message}
    if details is not None:
        body['details'] = details
    return JSONResponse(status_code=status, content={'error': body})


def create_app(client=None, database=None):
    @asynccontextmanager
    async def lifespan(app):
        mode = app_mode()
        selected_database = database or os.getenv('FEATURE_DATABASE', DEMO_DATABASE if mode == 'demo' else 'apticonduite_features')
        if client is None and mode == 'demo' and selected_database != DEMO_DATABASE:
            raise ValueError('Demo cannot connect to a non-demo database')
        app.state.mongo_client = client if client is not None else mongo_client()
        app.state.database = selected_database
        app.state.mode = mode
        try:
            if client is None and mode == 'demo':
                from feature_store.demo import seed_demo
                seed_demo(app.state.mongo_client)
            yield
        finally:
            if client is None:
                app.state.mongo_client.close()

    app = FastAPI(title='Driving Simulator Physiological Data Management & Processing', version='1.0.0', lifespan=lifespan,
                  responses={code: {'model': ErrorResponse} for code in [404, 409, 422, 503]})

    @app.exception_handler(DuplicateKeyError)
    async def duplicate(request, exc):
        return error(409, 'duplicate_record', 'A record with this source identity already exists')

    @app.exception_handler(PyMongoError)
    async def database_error(request, exc):
        return error(503, 'database_unavailable', 'Database temporarily unavailable')

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Omit input values and exception contexts, which can contain PII.
        details = [{'location': list(e['loc']), 'type': e['type']} for e in exc.errors()]
        return error(422, 'invalid_request', 'Request validation failed', details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        return error(exc.status_code, 'not_found' if exc.status_code == 404 else 'request_error', str(exc.detail))

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return error(500, 'internal_error', 'An internal error occurred')

    @app.get('/health', response_model=HealthResponse)
    def health(request: Request):
        request.app.state.mongo_client.admin.command('ping')
        return {'status': 'ok'}

    app.include_router(router)
    return app


app = create_app()
