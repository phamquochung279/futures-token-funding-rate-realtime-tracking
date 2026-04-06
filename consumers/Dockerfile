FROM python:3.9-slim

WORKDIR /app
COPY kafka_consumer.py .
RUN pip install --no-cache-dir kafka-python==2.0.2 psycopg2-binary

CMD ["python", "kafka_consumer.py"]
