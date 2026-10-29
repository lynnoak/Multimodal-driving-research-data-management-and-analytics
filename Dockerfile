FROM python:3.11-slim
WORKDIR /service
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY feature_store ./feature_store
COPY app ./app
RUN useradd --create-home api
USER api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
