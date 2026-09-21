-- ============================================================================
-- Growth metrics -- SYNTHETIC users/events; order value anchored to the real,
-- cited food-delivery AOV benchmark (see README > Data Assumptions).
--
-- MySQL has no DATE_TRUNC (Postgres-only): month truncation uses DATE_FORMAT/
-- STR_TO_DATE; week truncation uses DATE_SUB(..., INTERVAL WEEKDAY(...) DAY) to get a
-- Monday-start week, matching Postgres' DATE_TRUNC('week', ...) convention.
-- ============================================================================

USE food_delivery_analytics;

-- 5a. DAU (daily, raw series -- average this in your BI tool or see the monthly rollup below)
SELECT DATE(event_ts) AS activity_date, COUNT(DISTINCT user_id) AS dau
FROM synthetic_funnel_events
WHERE stage = 'app_open'
GROUP BY activity_date
ORDER BY activity_date;

-- 5b. WAU by ISO week (Monday-start)
SELECT DATE_SUB(DATE(event_ts), INTERVAL WEEKDAY(event_ts) DAY) AS week_start,
       COUNT(DISTINCT user_id) AS wau
FROM synthetic_funnel_events
WHERE stage = 'app_open'
GROUP BY week_start
ORDER BY week_start;

-- 5c. Monthly rollup: DAU (avg), WAU (avg), MAU, orders, orders/ordering-user, orders/MAU,
-- AOV, revenue, revenue/MAU, within-month repeat-order rate
WITH daily AS (
    SELECT DATE(event_ts) AS d,
           STR_TO_DATE(DATE_FORMAT(event_ts, '%Y-%m-01'), '%Y-%m-%d') AS month,
           COUNT(DISTINCT user_id) AS dau
    FROM synthetic_funnel_events WHERE stage = 'app_open'
    GROUP BY d, month
),
weekly AS (
    SELECT DATE_SUB(DATE(event_ts), INTERVAL WEEKDAY(event_ts) DAY) AS w,
           STR_TO_DATE(DATE_FORMAT(event_ts, '%Y-%m-01'), '%Y-%m-%d') AS month,
           COUNT(DISTINCT user_id) AS wau
    FROM synthetic_funnel_events WHERE stage = 'app_open'
    GROUP BY w, month
),
monthly_active AS (
    SELECT STR_TO_DATE(DATE_FORMAT(event_ts, '%Y-%m-01'), '%Y-%m-%d') AS month,
           COUNT(DISTINCT user_id) AS mau
    FROM synthetic_funnel_events WHERE stage = 'app_open'
    GROUP BY month
),
orders_monthly AS (
    SELECT STR_TO_DATE(DATE_FORMAT(order_ts, '%Y-%m-01'), '%Y-%m-%d') AS month,
           COUNT(*) AS orders,
           COUNT(DISTINCT user_id) AS ordering_users,
           ROUND(AVG(order_value), 2) AS aov,
           ROUND(SUM(order_value), 2) AS revenue
    FROM synthetic_orders
    GROUP BY month
),
repeat_within_month AS (
    SELECT STR_TO_DATE(DATE_FORMAT(order_ts, '%Y-%m-01'), '%Y-%m-%d') AS month, user_id, COUNT(*) AS n_orders
    FROM synthetic_orders
    GROUP BY month, user_id
),
repeat_rate AS (
    SELECT month, ROUND(AVG(CASE WHEN n_orders >= 2 THEN 1.0 ELSE 0 END), 4) AS repeat_order_rate_within_month
    FROM repeat_within_month
    GROUP BY month
)
SELECT
    ma.month,
    (SELECT ROUND(AVG(dau), 1) FROM daily d WHERE d.month = ma.month) AS dau_avg,
    (SELECT ROUND(AVG(wau), 1) FROM weekly w WHERE w.month = ma.month) AS wau_avg,
    ma.mau,
    om.orders,
    om.ordering_users,
    ROUND(om.orders / NULLIF(om.ordering_users, 0), 2) AS orders_per_ordering_user,
    ROUND(om.orders / NULLIF(ma.mau, 0), 2) AS orders_per_mau,
    om.aov,
    om.revenue,
    ROUND(om.revenue / NULLIF(ma.mau, 0), 2) AS revenue_per_mau,
    rr.repeat_order_rate_within_month
FROM monthly_active ma
LEFT JOIN orders_monthly om ON om.month = ma.month
LEFT JOIN repeat_rate rr ON rr.month = ma.month
ORDER BY ma.month;

-- 5d. Lifetime repeat-customer rate (all-time, not within-month)
SELECT
    ROUND(100.0 * AVG(CASE WHEN n_orders >= 2 THEN 1 ELSE 0 END), 2) AS lifetime_repeat_customer_pct
FROM (
    SELECT user_id, COUNT(*) AS n_orders
    FROM synthetic_orders
    GROUP BY user_id
) t;
