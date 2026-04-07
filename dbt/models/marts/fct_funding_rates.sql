WITH stg AS (
    SELECT * FROM {{ ref('stg_funding_rates') }}
)

SELECT
    id,
    base_asset_id,
    base_asset,
    funding_rate,
    -- Categories based on ATX alert thresholds: -0.3, -0.8, -1.2, -2
    CASE
        WHEN funding_rate <= -2.0  THEN 'critical'        -- most attractive, top alert
        WHEN funding_rate <= -1.2  THEN 'very_negative'
        WHEN funding_rate <= -0.8  THEN 'negative'
        WHEN funding_rate <= -0.3  THEN 'watch'           -- entry threshold per strategy
        WHEN funding_rate < 0      THEN 'slightly_negative'
        WHEN funding_rate = 0      THEN 'neutral'
        ELSE                            'positive'        -- shorts pay longs
    END                             AS funding_rate_category,
    -- Flag tokens worthy of notifying VIP clients
    funding_rate <= -0.3            AS is_attractive,
    event_at,
    ingested_at
FROM stg
