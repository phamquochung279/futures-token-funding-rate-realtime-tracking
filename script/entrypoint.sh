#!/bin/bash
set -e

if [ -e "/opt/airflow/requirements-dags.txt" ]; then
  python -m pip install --user -q -r /opt/airflow/requirements-dags.txt
fi

airflow db upgrade
airflow users create \
  --username admin \
  --firstname admin \
  --lastname admin \
  --role Admin \
  --email admin@example.com \
  --password admin \
  2>/dev/null || true

exec airflow webserver