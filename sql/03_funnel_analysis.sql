-- ============================================================================
-- Funnel analysis -- SYNTHETIC DATA, calibrated to cited benchmarks (README > Data
-- Assumptions). Two views are reported:
--   (a) "first session" -- each user's earliest session only. This is the standard
--       new-user activation funnel and is the number that should be compared against
--       published acquisition-funnel benchmarks.
--   (b) "blended" -- every session, including repeat/reorder sessions from returning
--       (especially power) users, which convert far higher. Blended > first-session is
--       expected and is itself a finding (see README).
--
-- MySQL has no DISTINCT ON (Postgres-only) -- ROW_NUMBER() + a filter does the same job.
-- ============================================================================

USE food_delivery_analytics;

WITH session_agg AS (
    SELECT
        session_id,
        MIN(user_id)     AS user_id,
        MIN(event_ts)    AS start_ts,
        MAX(stage_order) AS max_stage_order
    FROM synthetic_funnel_events
    GROUP BY session_id
),
session_ranked AS (
    SELECT session_id, user_id, start_ts, max_stage_order,
           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY start_ts) AS rn
    FROM session_agg
),
first_session AS (
    SELECT session_id, user_id, start_ts, max_stage_order
    FROM session_ranked
    WHERE rn = 1
),
stage_lookup AS (
    SELECT * FROM (VALUES
        ROW('app_open', 0), ROW('browse', 1), ROW('view_restaurant', 2),
        ROW('add_to_cart', 3), ROW('checkout_start', 4), ROW('order_placed', 5)
    ) AS t (stage, stage_order)
),

-- (a) first-session funnel
first_session_counts AS (
    SELECT sl.stage, sl.stage_order, COUNT(fs.session_id) AS sessions
    FROM stage_lookup sl
    LEFT JOIN first_session fs ON fs.max_stage_order >= sl.stage_order
    GROUP BY sl.stage, sl.stage_order
),
-- (b) blended funnel (every session)
blended_counts AS (
    SELECT sl.stage, sl.stage_order, COUNT(sa.session_id) AS sessions
    FROM stage_lookup sl
    LEFT JOIN session_agg sa ON sa.max_stage_order >= sl.stage_order
    GROUP BY sl.stage, sl.stage_order
)

SELECT 'first_session' AS funnel_view, stage, stage_order, sessions,
       ROUND(sessions / LAG(sessions) OVER (ORDER BY stage_order), 4) AS conversion_from_prev_stage,
       ROUND(sessions / FIRST_VALUE(sessions) OVER (ORDER BY stage_order), 4) AS conversion_from_top
FROM first_session_counts
UNION ALL
SELECT 'blended' AS funnel_view, stage, stage_order, sessions,
       ROUND(sessions / LAG(sessions) OVER (ORDER BY stage_order), 4) AS conversion_from_prev_stage,
       ROUND(sessions / FIRST_VALUE(sessions) OVER (ORDER BY stage_order), 4) AS conversion_from_top
FROM blended_counts
ORDER BY funnel_view, stage_order;
