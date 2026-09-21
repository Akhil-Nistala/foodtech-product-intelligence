-- ============================================================================
-- Delivery performance analysis -- REAL DATA (Kaggle food-delivery dataset).
-- On-time SLA: time_taken_min <= 30 (see README > Data Assumptions for the source of
-- the 30-45 minute "normal conditions" delivery window this threshold is drawn from).
--
-- MySQL has no built-in CORR() aggregate or PERCENTILE_CONT() -- both are computed by
-- hand below (Pearson's r from raw sums; the median via a window-function rank trick).
-- ============================================================================

USE food_delivery_analytics;

-- 2a. Overall on-time %, average and median delivery time
SELECT
    COUNT(*) AS total_orders,
    ROUND(100.0 * AVG(on_time), 2) AS on_time_pct,
    ROUND(AVG(time_taken_min), 2) AS avg_time_taken_min,
    (SELECT ROUND(AVG(time_taken_min), 2)
     FROM (
         SELECT time_taken_min,
                ROW_NUMBER() OVER (ORDER BY time_taken_min) AS rn,
                COUNT(*) OVER () AS cnt
         FROM real_orders
     ) ranked
     WHERE rn IN (FLOOR((cnt + 1) / 2), FLOOR((cnt + 2) / 2))
    ) AS median_time_taken_min
FROM real_orders;

-- 2b. On-time % and average delivery time by traffic density
SELECT
    traffic_density,
    COUNT(*) AS orders,
    ROUND(100.0 * AVG(on_time), 2) AS on_time_pct,
    ROUND(AVG(time_taken_min), 2) AS avg_time_taken_min
FROM real_orders
WHERE traffic_density IS NOT NULL
GROUP BY traffic_density
ORDER BY FIELD(traffic_density, 'Low', 'Medium', 'High', 'Jam');

-- 2c. On-time % and average delivery time by weather condition
SELECT
    weather,
    COUNT(*) AS orders,
    ROUND(100.0 * AVG(on_time), 2) AS on_time_pct,
    ROUND(AVG(time_taken_min), 2) AS avg_time_taken_min
FROM real_orders
WHERE weather IS NOT NULL
GROUP BY weather
ORDER BY on_time_pct;

-- 2d. On-time % by city type and by festival flag (delay-cause breakdown)
SELECT city_type,
       COUNT(*) AS orders,
       ROUND(100.0 * AVG(on_time), 2) AS on_time_pct,
       ROUND(AVG(time_taken_min), 2) AS avg_time_taken_min
FROM real_orders
WHERE city_type IS NOT NULL
GROUP BY city_type
ORDER BY on_time_pct;

SELECT festival,
       COUNT(*) AS orders,
       ROUND(100.0 * AVG(on_time), 2) AS on_time_pct,
       ROUND(AVG(time_taken_min), 2) AS avg_time_taken_min
FROM real_orders
WHERE festival IS NOT NULL
GROUP BY festival;

-- 2e. Correlation of delivery time with distance and with an ordinal traffic-severity
-- score (Low=0 .. Jam=3), computed by hand from raw sums (Pearson's r formula) since
-- MySQL has no CORR() aggregate. For a rank-based (Spearman) coefficient or an ANOVA
-- F-test across weather categories, run python/analysis.py::delivery_performance, which
-- uses scipy and reports p-values alongside each statistic
-- (see output/tables/delivery_stats_summary.csv).
WITH base AS (
    SELECT
        distance_km,
        time_taken_min,
        multiple_deliveries,
        CASE traffic_density WHEN 'Low' THEN 0 WHEN 'Medium' THEN 1 WHEN 'High' THEN 2 WHEN 'Jam' THEN 3 END AS traffic_ordinal
    FROM real_orders
    WHERE distance_km IS NOT NULL AND traffic_density IS NOT NULL AND multiple_deliveries IS NOT NULL
),
sums AS (
    SELECT
        COUNT(*) AS n,
        SUM(distance_km) AS sx, SUM(time_taken_min) AS sy, SUM(distance_km * time_taken_min) AS sxy,
        SUM(distance_km * distance_km) AS sxx, SUM(time_taken_min * time_taken_min) AS syy,
        SUM(traffic_ordinal) AS stx, SUM(traffic_ordinal * time_taken_min) AS stxy, SUM(traffic_ordinal * traffic_ordinal) AS stxx,
        SUM(multiple_deliveries) AS smx, SUM(multiple_deliveries * time_taken_min) AS smxy, SUM(multiple_deliveries * multiple_deliveries) AS smxx
    FROM base
)
SELECT
    ROUND((n * sxy - sx * sy) / SQRT((n * sxx - sx * sx) * (n * syy - sy * sy)), 4) AS corr_distance_vs_time,
    ROUND((n * stxy - stx * sy) / SQRT((n * stxx - stx * stx) * (n * syy - sy * sy)), 4) AS corr_traffic_ordinal_vs_time,
    ROUND((n * smxy - smx * sy) / SQRT((n * smxx - smx * smx) * (n * syy - sy * sy)), 4) AS corr_multiple_deliveries_vs_time
FROM sums;

-- 2f. Delay-cause interaction: average delivery time by traffic x weather (top delay combos)
SELECT
    traffic_density, weather,
    COUNT(*) AS orders,
    ROUND(AVG(time_taken_min), 2) AS avg_time_taken_min,
    ROUND(100.0 * AVG(on_time), 2) AS on_time_pct
FROM real_orders
WHERE traffic_density IS NOT NULL AND weather IS NOT NULL
GROUP BY traffic_density, weather
HAVING COUNT(*) >= 30
ORDER BY avg_time_taken_min DESC
LIMIT 10;
