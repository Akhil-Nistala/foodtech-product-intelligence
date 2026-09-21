"""
Core analysis functions shared by the pipeline script (this file's __main__) and the
Jupyter notebook (notebooks/analysis.ipynb imports these directly so the notebook and the
saved output/ tables never drift apart).

Sections, matching the project brief:
  1. funnel_analysis        - SYNTHETIC (funnel events, calibrated to cited benchmarks)
  2. cohort_retention        - SYNTHETIC
  3. growth_metrics          - SYNTHETIC (users/events) + REAL (AOV anchor already baked into synthetic order_value)
  4. delivery_performance    - REAL (Kaggle order-level dataset)
  5. ab_test                 - SYNTHETIC (simulated experiment)
"""
import numpy as np
import pandas as pd
from scipy import stats

CHART_COLORS = {
    "blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100",
    "magenta": "#e87ba4", "green": "#008300", "violet": "#4a3aa7", "red": "#e34948",
    "surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
    "grid": "#e1e0d9", "good": "#0ca30c", "critical": "#d03b3b",
}

FUNNEL_STAGES = ["app_open", "browse", "view_restaurant", "add_to_cart", "checkout_start", "order_placed"]


# ---------------------------------------------------------------------------
# 1. Funnel analysis (SYNTHETIC)
# ---------------------------------------------------------------------------
def _stage_table(session_stage_counts: pd.Series) -> pd.DataFrame:
    counts = session_stage_counts.reindex(FUNNEL_STAGES).fillna(0).astype(int)
    df = pd.DataFrame({"stage": FUNNEL_STAGES, "sessions": counts.values})
    df["conversion_from_prev_stage"] = (df["sessions"] / df["sessions"].shift(1)).fillna(1.0)
    df["dropoff_from_prev_stage"] = 1 - df["conversion_from_prev_stage"]
    df["conversion_from_top"] = df["sessions"] / df["sessions"].iloc[0]
    return df


def funnel_analysis(events: pd.DataFrame) -> dict:
    """Returns {'first_session': df, 'blended': df} -- see README for why both exist."""
    session_min_ts = events.groupby("session_id")["event_ts"].min()
    session_user = events.groupby("session_id")["user_id"].first()
    session_max_stage = events.groupby("session_id")["stage_order"].max()
    session_tbl = pd.DataFrame({
        "user_id": session_user, "start_ts": session_min_ts, "max_stage_order": session_max_stage,
    })

    first_session_ids = session_tbl.sort_values("start_ts").groupby("user_id").head(1).index
    first_events = events[events["session_id"].isin(first_session_ids)]

    blended_counts = events.groupby("stage")["session_id"].nunique()
    first_counts = first_events.groupby("stage")["session_id"].nunique()

    return {
        "first_session": _stage_table(first_counts),
        "blended": _stage_table(blended_counts),
    }


# ---------------------------------------------------------------------------
# 2. Cohort retention (SYNTHETIC)
# ---------------------------------------------------------------------------
def cohort_retention(users: pd.DataFrame, events: pd.DataFrame, analysis_end: pd.Timestamp) -> pd.DataFrame:
    opens = events[events["stage"] == "app_open"][["user_id", "event_ts"]].merge(
        users[["user_id", "signup_date"]], on="user_id"
    )
    opens["day_since_signup"] = (opens["event_ts"].dt.normalize() - opens["signup_date"]).dt.days
    users = users.copy()
    users["cohort_month"] = users["signup_date"].dt.to_period("M").astype(str)

    rows = []
    for cohort, cohort_users in users.groupby("cohort_month"):
        cohort_signup_date = cohort_users["signup_date"].iloc[0].to_period("M").to_timestamp()
        row = {"cohort_month": cohort, "cohort_size": len(cohort_users)}
        for d in (1, 7, 30):
            eligible = cohort_users[cohort_users["signup_date"] <= analysis_end - pd.Timedelta(days=d)]
            if len(eligible) == 0:
                row[f"D{d}_retention"] = np.nan
                continue
            active = opens[
                (opens["user_id"].isin(eligible["user_id"])) & (opens["day_since_signup"] == d)
            ]["user_id"].nunique()
            row[f"D{d}_retention"] = active / len(eligible)
            row[f"D{d}_eligible_users"] = len(eligible)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("cohort_month").reset_index(drop=True)


def overall_retention_curve(users: pd.DataFrame, events: pd.DataFrame, analysis_end: pd.Timestamp, max_day=45) -> pd.DataFrame:
    opens = events[events["stage"] == "app_open"][["user_id", "event_ts"]].merge(
        users[["user_id", "signup_date"]], on="user_id"
    )
    opens["day_since_signup"] = (opens["event_ts"].dt.normalize() - opens["signup_date"]).dt.days
    rows = []
    for d in range(1, max_day + 1):
        eligible = users[users["signup_date"] <= analysis_end - pd.Timedelta(days=d)]
        if len(eligible) == 0:
            continue
        active = opens[(opens["user_id"].isin(eligible["user_id"])) & (opens["day_since_signup"] == d)]["user_id"].nunique()
        rows.append({"day": d, "retention": active / len(eligible), "eligible_users": len(eligible)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Growth metrics (SYNTHETIC users/events; AOV anchored to real benchmark)
# ---------------------------------------------------------------------------
def growth_metrics(users: pd.DataFrame, events: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    opens = events[events["stage"] == "app_open"][["user_id", "event_ts"]].copy()
    opens["date"] = opens["event_ts"].dt.normalize()
    opens["month"] = opens["event_ts"].dt.to_period("M")

    daily_active = opens.groupby("date")["user_id"].nunique()
    dau_by_month = daily_active.groupby(daily_active.index.to_period("M")).mean()

    weekly_active = opens.groupby(opens["event_ts"].dt.to_period("W"))["user_id"].nunique()
    wau_by_month = weekly_active.groupby(weekly_active.index.asfreq("M")).mean()

    mau = opens.groupby("month")["user_id"].nunique()

    orders_m = orders.copy()
    orders_m["month"] = orders_m["order_ts"].dt.to_period("M")
    orders_per_month = orders_m.groupby("month").size()
    ordering_users_per_month = orders_m.groupby("month")["user_id"].nunique()
    aov_per_month = orders_m.groupby("month")["order_value"].mean()
    revenue_per_month = orders_m.groupby("month")["order_value"].sum()

    repeat_within_month = orders_m.groupby(["month", "user_id"]).size().reset_index(name="n")
    repeat_rate_month = repeat_within_month.groupby("month").apply(
        lambda g: (g["n"] >= 2).mean(), include_groups=False
    )

    out = pd.DataFrame({
        "DAU_avg": dau_by_month, "WAU_avg": wau_by_month, "MAU": mau,
        "orders": orders_per_month, "ordering_users": ordering_users_per_month,
        "orders_per_ordering_user": orders_per_month / ordering_users_per_month,
        "orders_per_MAU": orders_per_month / mau,
        "AOV": aov_per_month, "revenue": revenue_per_month,
        "revenue_per_MAU": revenue_per_month / mau,
        "repeat_order_rate_within_month": repeat_rate_month,
    })
    out = out.reindex(mau.index)  # MAU is the authoritative month index; drops WAU spillover buckets
    out.index = out.index.astype(str)
    out.index.name = "month"

    lifetime = orders.groupby("user_id").size()
    overall_repeat_rate = (lifetime >= 2).mean()
    out.attrs["lifetime_repeat_customer_rate"] = overall_repeat_rate
    return out.reset_index()


# ---------------------------------------------------------------------------
# 4. Delivery performance (REAL Kaggle data)
# ---------------------------------------------------------------------------
TRAFFIC_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Jam": 3}


def delivery_performance(real_df: pd.DataFrame) -> dict:
    df = real_df.copy()
    df["traffic_density"] = df["traffic_density"].str.strip()
    overall_on_time = df["on_time"].mean()

    by_traffic = df.groupby("traffic_density").agg(
        orders=("order_id", "count"), on_time_pct=("on_time", "mean"),
        avg_time_taken_min=("time_taken_min", "mean"),
    ).reindex(["Low", "Medium", "High", "Jam"]).dropna(how="all")

    by_weather = df.groupby("weather").agg(
        orders=("order_id", "count"), on_time_pct=("on_time", "mean"),
        avg_time_taken_min=("time_taken_min", "mean"),
    ).sort_values("on_time_pct")

    by_city = df.groupby("city_type").agg(
        orders=("order_id", "count"), on_time_pct=("on_time", "mean"),
        avg_time_taken_min=("time_taken_min", "mean"),
    ).sort_values("on_time_pct")

    by_festival = df.groupby("festival").agg(
        orders=("order_id", "count"), on_time_pct=("on_time", "mean"),
        avg_time_taken_min=("time_taken_min", "mean"),
    )

    # Correlations / significance tests
    d = df.dropna(subset=["distance_km", "time_taken_min"])
    r_distance, p_distance = stats.pearsonr(d["distance_km"], d["time_taken_min"])

    t2 = df.dropna(subset=["traffic_density", "time_taken_min"]).copy()
    t2["traffic_ordinal"] = t2["traffic_density"].map(TRAFFIC_ORDER)
    rho_traffic, p_traffic = stats.spearmanr(t2["traffic_ordinal"], t2["time_taken_min"])

    w = df.dropna(subset=["weather", "time_taken_min"])
    groups = [g["time_taken_min"].values for _, g in w.groupby("weather")]
    f_weather, p_weather = stats.f_oneway(*groups)

    md = df.dropna(subset=["multiple_deliveries", "time_taken_min"])
    r_multi, p_multi = stats.pearsonr(md["multiple_deliveries"], md["time_taken_min"])

    stats_summary = pd.DataFrame([
        {"test": "distance_km vs time_taken_min", "method": "Pearson r", "statistic": r_distance, "p_value": p_distance},
        {"test": "traffic_density (ordinal) vs time_taken_min", "method": "Spearman rho", "statistic": rho_traffic, "p_value": p_traffic},
        {"test": "weather vs time_taken_min", "method": "One-way ANOVA F", "statistic": f_weather, "p_value": p_weather},
        {"test": "multiple_deliveries vs time_taken_min", "method": "Pearson r", "statistic": r_multi, "p_value": p_multi},
    ])

    return {
        "overall_on_time_pct": overall_on_time,
        "by_traffic": by_traffic.reset_index(),
        "by_weather": by_weather.reset_index(),
        "by_city": by_city.reset_index(),
        "by_festival": by_festival.reset_index(),
        "stats_summary": stats_summary,
    }


# ---------------------------------------------------------------------------
# 5. A/B test (SYNTHETIC)
# ---------------------------------------------------------------------------
def ab_test_analysis(ab: pd.DataFrame) -> dict:
    g = ab.groupby("arm")["order_placed"].agg(["sum", "count"])
    n_c, x_c = int(g.loc["control", "count"]), int(g.loc["control", "sum"])
    n_t, x_t = int(g.loc["treatment", "count"]), int(g.loc["treatment", "sum"])
    p_c, p_t = x_c / n_c, x_t / n_t

    abs_lift = p_t - p_c
    rel_lift = abs_lift / p_c

    # Two-proportion pooled z-test
    p_pool = (x_c + x_t) / (n_c + n_t)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))
    z = (p_t - p_c) / se_pool
    p_value_z = 2 * stats.norm.sf(abs(z))  # survival function: numerically stable in the tail

    # Chi-square test of independence (cross-check)
    table = [[x_c, n_c - x_c], [x_t, n_t - x_t]]
    chi2, p_value_chi2, dof, _ = stats.chi2_contingency(table, correction=False)

    # 95% Wald CI on the difference in proportions
    se_diff = np.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    ci_low = abs_lift - 1.96 * se_diff
    ci_high = abs_lift + 1.96 * se_diff

    ship = (p_value_z < 0.05) and (ci_low > 0)

    result = {
        "n_control": n_c, "n_treatment": n_t,
        "conversions_control": x_c, "conversions_treatment": x_t,
        "rate_control": p_c, "rate_treatment": p_t,
        "absolute_lift_pp": abs_lift * 100, "relative_lift_pct": rel_lift * 100,
        "z_statistic": z, "p_value_ztest": p_value_z,
        "chi2_statistic": chi2, "p_value_chi2": p_value_chi2,
        "ci95_low_pp": ci_low * 100, "ci95_high_pp": ci_high * 100,
        "decision": "SHIP" if ship else "NO-SHIP",
    }
    return result
