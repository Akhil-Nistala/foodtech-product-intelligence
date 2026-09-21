"""
Cleans the REAL Kaggle "Food Delivery Time Prediction" dataset.

Source: gauravmalik26/food-delivery-dataset (Kaggle), mirrored (identical file hash) at
https://github.com/rajstories/FoodDelievery-Prediction/blob/main/Food%20delivery.csv
45,593 order-level rows collected March 2022, columns: delivery person, restaurant/
delivery geo-coordinates, order/pickup timestamps, weather, traffic, vehicle, city type,
and Time_taken(min).

Every column in the output of this script comes directly from that file. No columns are
invented here. See README.md > "Data Assumptions" for the full real-vs-synthetic split.
"""
import numpy as np
import pandas as pd

RAW_PATH = "data/raw/food_delivery_kaggle_raw.csv"
OUT_PATH = "data/processed/real_orders_clean.csv"

# On-time SLA threshold. The raw dataset has no "promised time" field, so we use the
# widely reported normal-conditions delivery window for Indian food-delivery apps
# (30-45 minutes) and take the lower/tighter bound -- the "30-minute delivery" figure
# both platforms have historically marketed -- as the on-time cutoff. Source: aggregated
# platform-comparison reporting, e.g. StartupTalky "Swiggy Vs Zomato" (startuptalky.com/
# zomato-vs-swiggy) and Aish4Aish "Swiggy vs Zomato 2026" (aish4aish.in) — both report
# a normal-conditions delivery band of 30-45 minutes.
ON_TIME_SLA_MIN = 30


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    str_cols = [
        "ID", "Delivery_person_ID", "Weatherconditions", "Road_traffic_density",
        "Type_of_order", "Type_of_vehicle", "Festival", "City",
    ]
    for c in str_cols:
        df[c] = df[c].astype(str).str.strip()
        df[c] = df[c].replace({"NaN": np.nan})

    df["Weatherconditions"] = df["Weatherconditions"].str.replace(
        "conditions ", "", regex=False
    )
    df["weather"] = df["Weatherconditions"].str.strip().replace({"NaN": np.nan})
    df["traffic_density"] = df["Road_traffic_density"]
    df["order_type"] = df["Type_of_order"]
    df["vehicle_type"] = df["Type_of_vehicle"]
    df["festival"] = df["Festival"]
    df["city_type"] = df["City"]

    for c in ["Delivery_person_Age", "Delivery_person_Ratings", "multiple_deliveries"]:
        df[c] = pd.to_numeric(df[c].astype(str).str.strip(), errors="coerce")

    df["time_taken_min"] = (
        df["Time_taken(min)"].astype(str).str.replace("(min) ", "", regex=False)
    )
    df["time_taken_min"] = pd.to_numeric(df["time_taken_min"], errors="coerce")

    df["order_date"] = pd.to_datetime(df["Order_Date"], format="%d-%m-%Y", errors="coerce")
    time_ordered = pd.to_datetime(
        df["Time_Orderd"].astype(str).str.strip(), format="%H:%M:%S", errors="coerce"
    ).dt.time
    time_picked = pd.to_datetime(
        df["Time_Order_picked"].astype(str).str.strip(), format="%H:%M:%S", errors="coerce"
    ).dt.time

    def combine(date, t):
        if pd.isna(date) or t is None or pd.isna(t):
            return pd.NaT
        return pd.Timestamp.combine(date, t)

    df["order_datetime"] = [combine(d, t) for d, t in zip(df["order_date"], time_ordered)]
    df["pickup_datetime"] = [combine(d, t) for d, t in zip(df["order_date"], time_picked)]
    crosses_midnight = df["pickup_datetime"] < df["order_datetime"]
    df.loc[crosses_midnight, "pickup_datetime"] += pd.Timedelta(days=1)

    df["prep_time_min"] = (
        df["pickup_datetime"] - df["order_datetime"]
    ).dt.total_seconds() / 60.0
    df.loc[(df["prep_time_min"] < 0) | (df["prep_time_min"] > 120), "prep_time_min"] = np.nan

    df["distance_km"] = haversine_km(
        df["Restaurant_latitude"], df["Restaurant_longitude"],
        df["Delivery_location_latitude"], df["Delivery_location_longitude"],
    ).abs()
    # A handful of rows carry corrupted (near-zero / out-of-range) coordinates in the
    # raw file; drop implausible distances (>50km, which is not a realistic single-city
    # food-delivery trip) rather than impute them.
    df.loc[(df["distance_km"] <= 0.05) | (df["distance_km"] > 50), "distance_km"] = np.nan

    df["on_time"] = df["time_taken_min"] <= ON_TIME_SLA_MIN

    keep = [
        "ID", "Delivery_person_ID", "Delivery_person_Age", "Delivery_person_Ratings",
        "order_datetime", "pickup_datetime", "prep_time_min", "distance_km",
        "weather", "traffic_density", "Vehicle_condition", "order_type", "vehicle_type",
        "multiple_deliveries", "festival", "city_type", "time_taken_min", "on_time",
    ]
    out = df[keep].rename(columns={
        "ID": "order_id",
        "Delivery_person_ID": "delivery_person_id",
        "Delivery_person_Age": "delivery_person_age",
        "Delivery_person_Ratings": "delivery_person_rating",
        "Vehicle_condition": "vehicle_condition",
    })
    return out


if __name__ == "__main__":
    raw = pd.read_csv(RAW_PATH)
    cleaned = clean(raw)
    cleaned.to_csv(OUT_PATH, index=False)
    print(f"rows in: {len(raw)}  rows out: {len(cleaned)}")
    print(cleaned.isna().mean().round(3).sort_values(ascending=False).head(10))
    print(cleaned[["time_taken_min", "distance_km", "prep_time_min"]].describe())
