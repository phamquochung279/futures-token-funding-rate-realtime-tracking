WITH source AS (
    SELECT * FROM {{ source('trading', 'funding_rates') }}
)

SELECT
    id,
    base_asset_id,
    base_asset,
    funding_rate,
    -- Convert event_time from milliseconds epoch to proper timestamp
    TO_TIMESTAMP(event_time / 1000.0)   AS event_at,
    ingested_at
FROM source
WHERE funding_rate IS NOT NULL
