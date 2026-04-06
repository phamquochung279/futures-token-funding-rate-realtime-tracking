#!/bin/bash
set -e

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