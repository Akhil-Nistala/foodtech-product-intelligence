-- ============================================================================
-- Schema for the food-delivery funnel & experimentation analytics project.
-- Target: MySQL 8.0+ (requires window-function and CTE support, both MySQL 8).
--
-- Table provenance (see README.md > "Data Assumptions" for full detail):
--   real_orders             REAL   -- Kaggle "Food Delivery Time Prediction" dataset
--   synthetic_users          SYNTHETIC
--   synthetic_funnel_events  SYNTHETIC
--   synthetic_orders         SYNTHETIC
--   synthetic_ab_test        SYNTHETIC
--
-- Targets MySQL because that's the database actually available to run and demo
-- end-to-end (the original brief specified PostgreSQL; a small number of comments below
-- note where MySQL syntax had to diverge from it).
-- ============================================================================

CREATE DATABASE IF NOT EXISTS food_delivery_analytics;
USE food_delivery_analytics;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS synthetic_ab_test;
DROP TABLE IF EXISTS synthetic_orders;
DROP TABLE IF EXISTS synthetic_funnel_events;
DROP TABLE IF EXISTS synthetic_users;
DROP TABLE IF EXISTS real_orders;
SET FOREIGN_KEY_CHECKS = 1;

-- REAL: one row per delivered order, from the Kaggle dataset (45,593 rows, March 2022).
CREATE TABLE real_orders (
    order_id                VARCHAR(32) PRIMARY KEY,
    delivery_person_id      VARCHAR(32),
    delivery_person_age     DECIMAL(5,1),
    delivery_person_rating  DECIMAL(3,1),
    order_datetime          DATETIME,
    pickup_datetime         DATETIME,
    prep_time_min           DECIMAL(6,2),
    distance_km             DECIMAL(8,3),
    weather                 VARCHAR(32),
    traffic_density         VARCHAR(16),   -- Low / Medium / High / Jam
    vehicle_condition       INT,
    order_type               VARCHAR(16),   -- Snack / Drinks / Buffet / Meal
    vehicle_type             VARCHAR(32),
    multiple_deliveries      DECIMAL(3,1),
    festival                 VARCHAR(8),    -- Yes / No
    city_type                VARCHAR(16),   -- Urban / Metropolitian / Semi-Urban
    time_taken_min           DECIMAL(6,2),
    on_time                  TINYINT(1)     -- time_taken_min <= 30 (see README for SLA source)
) ENGINE=InnoDB;
CREATE INDEX idx_real_orders_traffic ON real_orders (traffic_density);
CREATE INDEX idx_real_orders_weather ON real_orders (weather);

-- SYNTHETIC: one row per simulated signed-up user.
CREATE TABLE synthetic_users (
    user_id               VARCHAR(16) PRIMARY KEY,
    signup_date           DATE,
    city_tier             VARCHAR(16),   -- Metro / Tier-1 / Tier-2
    platform               VARCHAR(8),    -- iOS / Android
    acquisition_channel    VARCHAR(32),
    is_power_user           TINYINT(1)
) ENGINE=InnoDB;

-- SYNTHETIC: one row per funnel-stage event reached within a session.
-- A session that reaches "checkout_start" has 5 rows (app_open..checkout_start); a
-- session that reaches "order_placed" has all 6 rows. stage_order lets you find the
-- deepest stage per session without a CASE expression.
CREATE TABLE synthetic_funnel_events (
    session_id   VARCHAR(24),
    user_id      VARCHAR(16),
    event_ts     DATETIME,
    stage        VARCHAR(24),   -- app_open / browse / view_restaurant / add_to_cart / checkout_start / order_placed
    stage_order  TINYINT,       -- 0..5, matches the list order above
    PRIMARY KEY (session_id, stage),
    CONSTRAINT fk_funnel_events_user FOREIGN KEY (user_id) REFERENCES synthetic_users(user_id)
) ENGINE=InnoDB;
CREATE INDEX idx_funnel_events_user ON synthetic_funnel_events (user_id);
CREATE INDEX idx_funnel_events_stage ON synthetic_funnel_events (stage);
CREATE INDEX idx_funnel_events_ts ON synthetic_funnel_events (event_ts);

-- SYNTHETIC: one row per completed order (the subset of sessions reaching order_placed).
CREATE TABLE synthetic_orders (
    order_id      VARCHAR(16) PRIMARY KEY,
    session_id    VARCHAR(24),
    user_id       VARCHAR(16),
    order_ts      DATETIME,
    order_value   DECIMAL(9,2),
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES synthetic_users(user_id)
) ENGINE=InnoDB;
CREATE INDEX idx_synthetic_orders_user ON synthetic_orders (user_id);
CREATE INDEX idx_synthetic_orders_ts ON synthetic_orders (order_ts);

-- SYNTHETIC: one row per simulated checkout-start session in the A/B test window.
CREATE TABLE synthetic_ab_test (
    checkout_session_id  VARCHAR(16) PRIMARY KEY,
    arm                   VARCHAR(16),   -- control / treatment
    checkout_start_ts     DATETIME,
    order_placed          TINYINT(1)
) ENGINE=InnoDB;
CREATE INDEX idx_ab_test_arm ON synthetic_ab_test (arm);

-- Standard-normal CDF via the Zelen & Severo (1964) polynomial approximation, used by
-- 06_ab_test.sql to turn a z-statistic into a two-sided p-value without extensions.
DROP FUNCTION IF EXISTS norm_cdf;
DELIMITER $$
CREATE FUNCTION norm_cdf(x DOUBLE) RETURNS DOUBLE DETERMINISTIC
BEGIN
    DECLARE t DOUBLE;
    DECLARE y DOUBLE;
    DECLARE p_ DOUBLE DEFAULT 0.2316419;
    DECLARE b1 DOUBLE DEFAULT 0.319381530;
    DECLARE b2 DOUBLE DEFAULT -0.356563782;
    DECLARE b3 DOUBLE DEFAULT 1.781477937;
    DECLARE b4 DOUBLE DEFAULT -1.821255978;
    DECLARE b5 DOUBLE DEFAULT 1.330274429;
    DECLARE ax DOUBLE;
    DECLARE phi DOUBLE;
    DECLARE result DOUBLE;

    SET ax = ABS(x);
    SET t = 1.0 / (1.0 + p_ * ax);
    SET phi = (1.0 / SQRT(2 * PI())) * EXP(-0.5 * ax * ax);
    SET y = t * (b1 + t * (b2 + t * (b3 + t * (b4 + t * b5))));
    SET result = 1.0 - phi * y;
    IF x < 0 THEN
        SET result = 1.0 - result;
    END IF;
    RETURN result;
END$$
DELIMITER ;

-- Upper-tail P(Z > x), same approximation as norm_cdf() but returned directly as
-- phi(x)*y rather than via 1 - CDF -- for large x, 1 - CDF(x) underflows to exactly 0
-- in double precision (catastrophic cancellation: CDF(x) rounds to exactly 1.0), which
-- silently zeroes out any two-sided p-value computed from a z-statistic much above ~6.
-- 06_ab_test.sql uses this, not norm_cdf, for that reason (mirrors why
-- python/analysis.py uses scipy.stats.norm.sf() instead of 1 - norm.cdf()).
DROP FUNCTION IF EXISTS norm_sf;
DELIMITER $$
CREATE FUNCTION norm_sf(x DOUBLE) RETURNS DOUBLE DETERMINISTIC
BEGIN
    DECLARE t DOUBLE;
    DECLARE y DOUBLE;
    DECLARE p_ DOUBLE DEFAULT 0.2316419;
    DECLARE b1 DOUBLE DEFAULT 0.319381530;
    DECLARE b2 DOUBLE DEFAULT -0.356563782;
    DECLARE b3 DOUBLE DEFAULT 1.781477937;
    DECLARE b4 DOUBLE DEFAULT -1.821255978;
    DECLARE b5 DOUBLE DEFAULT 1.330274429;
    DECLARE ax DOUBLE;
    DECLARE phi DOUBLE;
    DECLARE tail DOUBLE;

    SET ax = ABS(x);
    SET t = 1.0 / (1.0 + p_ * ax);
    SET phi = (1.0 / SQRT(2 * PI())) * EXP(-0.5 * ax * ax);
    SET y = t * (b1 + t * (b2 + t * (b3 + t * (b4 + t * b5))));
    SET tail = phi * y;
    IF x >= 0 THEN
        RETURN tail;
    ELSE
        RETURN 1.0 - tail;
    END IF;
END$$
DELIMITER ;
