-- ============================================================================
-- Loads the cleaned CSVs (produced by python/run_pipeline.py) into MySQL.
--
-- Run with (from the project root, so the relative paths below resolve):
--   mysql --local-infile=1 -u analytics -p food_delivery_analytics < sql/01_load_data.sql
--
-- Requires local_infile enabled SERVER-side too (resets on every MySQL restart,
-- since it's a session/global runtime setting, not persisted in my.ini here):
--   mysql -u root -p -e "SET GLOBAL local_infile = 1;"
--
-- CSV booleans are written as the literal strings "True"/"False" (pandas' default),
-- not 0/1 -- the SET clauses below convert those explicitly. The CSVs also have
-- Windows-style \r\n line endings, which leaves a trailing \r glued onto the LAST
-- field of every row once split on '\n' alone -- TRIM(TRAILING '\r' FROM ...) strips
-- it (MySQL's plain TRIM() only strips spaces, not \r, so this must be explicit).
-- Empty CSV fields (real, missing values in the Kaggle data) become SQL NULL via
-- NULLIF(@var, '') rather than being stored as empty strings.
-- ============================================================================

USE food_delivery_analytics;

LOAD DATA LOCAL INFILE 'data/processed/real_orders_clean.csv'
INTO TABLE real_orders
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(order_id, delivery_person_id, @age, @rating, @order_dt, @pickup_dt, @prep, @dist,
 @weather, @traffic, @vcond, @otype, @vtype, @multi, @festival, @city, @tt, @on_time)
SET
    delivery_person_age    = NULLIF(@age, ''),
    delivery_person_rating = NULLIF(@rating, ''),
    order_datetime          = NULLIF(@order_dt, ''),
    pickup_datetime          = NULLIF(@pickup_dt, ''),
    prep_time_min            = NULLIF(@prep, ''),
    distance_km               = NULLIF(@dist, ''),
    weather                    = NULLIF(@weather, ''),
    traffic_density             = NULLIF(@traffic, ''),
    vehicle_condition            = NULLIF(@vcond, ''),
    order_type                    = NULLIF(@otype, ''),
    vehicle_type                   = NULLIF(@vtype, ''),
    multiple_deliveries              = NULLIF(@multi, ''),
    festival                          = NULLIF(@festival, ''),
    city_type                          = NULLIF(@city, ''),
    time_taken_min                      = NULLIF(@tt, ''),
    on_time                              = (TRIM(TRAILING '\r' FROM @on_time) = 'True');

LOAD DATA LOCAL INFILE 'data/processed/synthetic_users.csv'
INTO TABLE synthetic_users
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(user_id, signup_date, city_tier, platform, acquisition_channel, @power)
SET is_power_user = (TRIM(TRAILING '\r' FROM @power) = 'True');

LOAD DATA LOCAL INFILE 'data/processed/synthetic_funnel_events.csv'
INTO TABLE synthetic_funnel_events
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(session_id, user_id, event_ts, stage, @stage_order)
SET stage_order = TRIM(TRAILING '\r' FROM @stage_order);

LOAD DATA LOCAL INFILE 'data/processed/synthetic_orders.csv'
INTO TABLE synthetic_orders
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(session_id, user_id, order_ts, order_value, @order_id)
SET order_id = TRIM(TRAILING '\r' FROM @order_id);

LOAD DATA LOCAL INFILE 'data/processed/synthetic_ab_test.csv'
INTO TABLE synthetic_ab_test
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(checkout_session_id, arm, checkout_start_ts, @placed)
SET order_placed = (TRIM(TRAILING '\r' FROM @placed) = 'True');

SELECT 'real_orders' AS tbl, COUNT(*) AS rows_loaded FROM real_orders
UNION ALL SELECT 'synthetic_users', COUNT(*) FROM synthetic_users
UNION ALL SELECT 'synthetic_funnel_events', COUNT(*) FROM synthetic_funnel_events
UNION ALL SELECT 'synthetic_orders', COUNT(*) FROM synthetic_orders
UNION ALL SELECT 'synthetic_ab_test', COUNT(*) FROM synthetic_ab_test;
