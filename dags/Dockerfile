FROM apache/airflow:2.6.0-python3.9

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
USER airflow

COPY requirements-dags.txt /opt/airflow/requirements-dags.txt
RUN pip install --no-cache-dir -r /opt/airflow/requirements-dags.txt
