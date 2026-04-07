FROM apache/airflow:2.6.0-python3.9

COPY requirements-dags.txt /opt/airflow/requirements-dags.txt
RUN pip install --no-cache-dir -r /opt/airflow/requirements-dags.txt
