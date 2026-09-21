-- ============================================================================
-- A/B test -- SYNTHETIC: control (existing multi-step checkout) vs. treatment
-- (simplified checkout). Two-proportion z-test computed in-SQL via the norm_cdf()
-- helper function defined in 00_schema.sql.
-- ============================================================================

USE food_delivery_analytics;

WITH arm_stats AS (
    SELECT
        arm,
        COUNT(*) AS n,
        SUM(order_placed) AS conversions
    FROM synthetic_ab_test
    GROUP BY arm
),
pivoted AS (
    SELECT
        MAX(CASE WHEN arm = 'control' THEN n END)           AS n_c,
        MAX(CASE WHEN arm = 'control' THEN conversions END) AS x_c,
        MAX(CASE WHEN arm = 'treatment' THEN n END)          AS n_t,
        MAX(CASE WHEN arm = 'treatment' THEN conversions END) AS x_t
    FROM arm_stats
),
calc AS (
    SELECT
        n_c, x_c, n_t, x_t,
        x_c / n_c AS p_c,
        x_t / n_t AS p_t
    FROM pivoted
),
z AS (
    SELECT *,
        (p_t - p_c) AS abs_lift,
        (p_t - p_c) / p_c AS rel_lift,
        (x_c + x_t) / (n_c + n_t) AS p_pool
    FROM calc
),
zstat AS (
    SELECT *,
        (p_t - p_c) / SQRT(p_pool * (1 - p_pool) * (1.0 / n_c + 1.0 / n_t)) AS z_statistic,
        SQRT(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t) AS se_diff
    FROM z
)
SELECT
    n_c AS n_control, n_t AS n_treatment,
    x_c AS conversions_control, x_t AS conversions_treatment,
    ROUND(p_c * 100, 2) AS rate_control_pct,
    ROUND(p_t * 100, 2) AS rate_treatment_pct,
    ROUND(abs_lift * 100, 2) AS absolute_lift_pp,
    ROUND(rel_lift * 100, 2) AS relative_lift_pct,
    ROUND(z_statistic, 3) AS z_statistic,
    2 * norm_sf(ABS(z_statistic)) AS p_value_two_sided,  -- norm_sf, not 1-norm_cdf: see 00_schema.sql comment
    ROUND((abs_lift - 1.96 * se_diff) * 100, 2) AS ci95_low_pp,
    ROUND((abs_lift + 1.96 * se_diff) * 100, 2) AS ci95_high_pp,
    CASE
        WHEN (2 * norm_sf(ABS(z_statistic))) < 0.05 AND (abs_lift - 1.96 * se_diff) > 0
        THEN 'SHIP' ELSE 'NO-SHIP'
    END AS decision
FROM zstat;

-- Chi-square test of independence, as a cross-check against the z-test above (for a
-- 2x2 table, chi2 = z^2, so the two should agree to rounding error).
WITH arm_stats AS (
    SELECT arm, COUNT(*) AS n, SUM(order_placed) AS conversions
    FROM synthetic_ab_test GROUP BY arm
),
pivoted AS (
    SELECT
        MAX(CASE WHEN arm = 'control' THEN n END)            AS n_c,
        MAX(CASE WHEN arm = 'control' THEN conversions END)  AS x_c,
        MAX(CASE WHEN arm = 'treatment' THEN n END)           AS n_t,
        MAX(CASE WHEN arm = 'treatment' THEN conversions END) AS x_t
    FROM arm_stats
),
expected AS (
    SELECT n_c, x_c, n_t, x_t,
           (n_c + n_t) AS n_total,
           (x_c + x_t) AS x_total
    FROM pivoted
),
chi AS (
    SELECT
        POWER(x_c - (n_c * x_total / n_total), 2) / (n_c * x_total / n_total)
      + POWER((n_c - x_c) - (n_c * (n_total - x_total) / n_total), 2) / (n_c * (n_total - x_total) / n_total)
      + POWER(x_t - (n_t * x_total / n_total), 2) / (n_t * x_total / n_total)
      + POWER((n_t - x_t) - (n_t * (n_total - x_total) / n_total), 2) / (n_t * (n_total - x_total) / n_total)
      AS chi2_statistic
    FROM expected
)
SELECT ROUND(chi2_statistic, 3) AS chi2_statistic,
       'compare to the z_statistic squared, above. df=1 critical value at alpha=0.05 is 3.841.' AS note
FROM chi;
