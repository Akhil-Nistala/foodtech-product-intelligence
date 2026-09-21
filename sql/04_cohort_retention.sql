-- ============================================================================
-- Cohort retention (D1 / D7 / D30) -- SYNTHETIC DATA, calibrated to cited benchmarks.
-- "N-day retention": % of a signup cohort that opens the app again on exactly day N
-- after signup (the standard Amplitude/Mixpanel-style definition).
--
-- MySQL has no DATE_TRUNC (Postgres-only) -- month truncation uses DATE_FORMAT/STR_TO_DATE.
-- ============================================================================

USE food_delivery_analytics;

WITH cohorts AS (
    SELECT user_id, signup_date, STR_TO_DATE(DATE_FORMAT(signup_date, '%Y-%m-01'), '%Y-%m-%d') AS cohort_month
    FROM synthetic_users
),
opens AS (
    SELECT DISTINCT user_id, DATE(event_ts) AS open_date
    FROM synthetic_funnel_events
    WHERE stage = 'app_open'
),
opens_with_offset AS (
    SELECT c.user_id, c.cohort_month, DATEDIFF(o.open_date, c.signup_date) AS day_since_signup
    FROM opens o
    JOIN cohorts c ON c.user_id = o.user_id
),
-- an analysis cutoff must be supplied so a cohort isn't penalized for not yet having
-- reached day N; replace with your own run date if re-running against fresh data
params AS (SELECT DATE('2024-09-30') AS analysis_end),
day_values AS (SELECT * FROM (VALUES ROW(1), ROW(7), ROW(30)) AS t(n)),
eligible AS (
    SELECT c.cohort_month, d.n, COUNT(*) AS eligible_users
    FROM cohorts c
    CROSS JOIN day_values d
    CROSS JOIN params p
    WHERE c.signup_date <= DATE_SUB(p.analysis_end, INTERVAL d.n DAY)
    GROUP BY c.cohort_month, d.n
),
active AS (
    SELECT cohort_month, day_since_signup AS n, COUNT(DISTINCT user_id) AS active_users
    FROM opens_with_offset
    WHERE day_since_signup IN (1, 7, 30)
    GROUP BY cohort_month, day_since_signup
)
SELECT
    e.cohort_month,
    e.n AS day_n,
    e.eligible_users,
    COALESCE(a.active_users, 0) AS active_users,
    ROUND(COALESCE(a.active_users, 0) / e.eligible_users, 4) AS retention_rate
FROM eligible e
LEFT JOIN active a ON a.cohort_month = e.cohort_month AND a.n = e.n
ORDER BY e.cohort_month, e.n;
