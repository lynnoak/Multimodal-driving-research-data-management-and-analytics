FROM python:3.11-slim
WORKDIR /workspace
ENV PYTHONPATH=/workspace
COPY requirements-dashboard.txt .
RUN pip install --no-cache-dir -r requirements-dashboard.txt
COPY dashboard ./dashboard
COPY .streamlit ./.streamlit
RUN useradd --create-home dashboard
USER dashboard
EXPOSE 8501
CMD ["streamlit", "run", "dashboard/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
