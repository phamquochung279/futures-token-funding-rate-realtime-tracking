from datetime import datetime, timezone, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'phamquochung279',
    'start_date': datetime(2026, 4, 5, 16, 0, tzinfo=timezone(timedelta(hours=7))),
}

def _fetch_one_funding_rate(row):
    """Fetch funding rate for a single token, with error handling and fallback."""
    import requests
    asset_id = row["assetId"]
    asset_code = row["assetCode"]
    api_url = (
        f"https://api.atxs.io/api/v1/futures/mark_price"
        f"?baseAssetId={asset_id}&quoteAssetId=617"
    )
    fallback = {
        "baseAssetId": asset_id,
        "baseAsset": asset_code,
        "fundingRate": None,
        "eventTime": None,
    }
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("data"):
                fd = data["data"]
                print(f"Successfully fetched funding rate for {asset_code}: {fd.get('fundingRate')}")
                return {
                    "baseAssetId": fd.get("baseAssetId") or asset_id,
                    "baseAsset": fd.get("baseAsset") or asset_code,
                    "fundingRate": fd.get("fundingRate"),
                    "eventTime": fd.get("eventTime"),
                }
            else:
                print(f"No data found for {asset_code}")
        else:
            print(f"API error for {asset_code}: status code {response.status_code}")
    except Exception as e:
        print(f"Request failed for {asset_code}: {e}")
    return fallback


def get_funding_rates():
    """Fetch funding rates of the full token list."""
    import time
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Step 1: Get the list of current futures listed tokens
    config_url = "https://api.atxs.io/api/v1/futures/config"
    try:
        cfg_resp = requests.get(config_url, timeout=10)
    except Exception:
        return

    if cfg_resp.status_code != 200:
        return

    try:
        cfg = cfg_resp.json()
    except Exception:
        return

    if cfg.get("status") != "success" or "data" not in cfg:
        return

    futures_listed_tokens = []
    for item in cfg["data"]:
        base_asset = item.get("baseAsset")
        base_asset_id = item.get("baseAssetId")
        if base_asset and base_asset_id:
            futures_listed_tokens.append(
                {"assetCode": str(base_asset), "assetId": int(base_asset_id)}
            )
    futures_listed_tokens.sort(key=lambda x: x["assetCode"])

    # Step 2: Fetch funding rates in parallel, one batch at a time
    BATCH_SIZE = 10
    BATCH_DELAY = 10 
    
    # seconds between batches (to avoid rate limiting)
    # there's only 7 assets left at the moment, so these 2 configs don't do anything.

    n = len(futures_listed_tokens)
    batches = [futures_listed_tokens[i:i + BATCH_SIZE] for i in range(0, n, BATCH_SIZE)]
    print(f"Starting funding rate API calls for {n} assets across {len(batches)} batches...")

    ok_count = 0
    with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
        for batch_idx, batch in enumerate(batches):
            batch_futures = {executor.submit(_fetch_one_funding_rate, row): row for row in batch}
            for fut in as_completed(batch_futures):
                record = fut.result()
                if record.get("fundingRate") is not None:
                    ok_count += 1
                yield record

            if batch_idx < len(batches) - 1:
                print(f"Batch {batch_idx + 1}/{len(batches)} done. Waiting {BATCH_DELAY}s before next batch...")
                time.sleep(BATCH_DELAY)

    print(f"Completed. Successfully retrieved funding rates for {ok_count} out of {n} assets")

def stream_data():
    import json
    import logging
    from kafka import KafkaProducer

    producer = KafkaProducer(
        bootstrap_servers=['broker:29092']
    )
    try:
        for record in get_funding_rates():
            key = record.get('baseAsset', '').encode('utf-8')
            producer.send('funding_rates', key=key, value=json.dumps(record).encode('utf-8'))
        producer.flush()
    except Exception as e:
        logging.error(f'An error occured: {e}')
        raise
    finally:
        producer.close()

# if __name__ == '__main__':
#     stream_data()

with DAG(
    'funding_rates_automation',
    default_args=default_args,
    schedule=timedelta(minutes=1),
    catchup=False,
) as dag:

    streaming_task = PythonOperator(
        task_id='stream_data_from_api',
        python_callable=stream_data
    )