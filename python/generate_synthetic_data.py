"""
Generates the SYNTHETIC layer of this project: users, daily funnel events
(app_open -> browse -> view_restaurant -> add_to_cart -> checkout_start -> order_placed),
and a checkout A/B test.

None of this is real. It exists because the real Kaggle dataset (see clean_real_data.py)
is order-level only and has no clickstream, no user identities, and no signup dates, so a
funnel/cohort/growth/A-B analysis cannot be built from it directly. Every generation
parameter below is calibrated to a cited, real industry figure -- see the comment next to
each constant, and README.md > "Data Assumptions" for the consolidated source list.

Modeling choices that are NOT sourced from a benchmark (they are internal-consistency
choices needed to make a synthetic generator work at all -- e.g. the specific parametric
retention decay curve, the power-user/casual-user mixture, the exact A/B lift used in the
demo test) are labeled "MODELING CHOICE" rather than presented as sourced.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

# ---------------------------------------------------------------------------
# Population & time window
# ---------------------------------------------------------------------------
N_USERS = 8000
SIGNUP_START = pd.Timestamp("2024-01-01")
SIGNUP_END = pd.Timestamp("2024-06-30")
ANALYSIS_END = pd.Timestamp("2024-09-30")  # observation cutoff for growth/cohort metrics

CITY_TIERS = ["Metro", "Tier-1", "Tier-2"]
CITY_WEIGHTS = [0.45, 0.35, 0.20]  # MODELING CHOICE: skew toward metro, typical of Indian food-delivery penetration

# ---------------------------------------------------------------------------
# Retention curve (N-day retention: % of a signup cohort that opens the app again on
# exactly day N after signup). Cross-vertical mobile benchmark: D1 ~25-26%, D7 ~11-13%,
# D30 ~5-7% (Adjust "2026 Mobile App Trends Report", as summarized by mwm.ai
# "Retention (D1/D7/D30) - Mobile App Retention Benchmarks" and prooflytics.io "D7 and D30
# Retention Benchmarks by App Category"). No food-delivery-specific D1/D7/D30 breakout was
# publicly available (this is exactly the gap this project's README calls out), so we use
# the closest published proxy vertical -- e-commerce/retail, D30 ~3-6% -- and anchor to the
# midpoints below.
D1_RETENTION = 0.26
D7_RETENTION = 0.12
D30_RETENTION = 0.05
LONG_RUN_FLOOR = 0.008  # MODELING CHOICE: slow decay continues past day 30, floors out

# MODELING CHOICE: an engaged minority ("power users") decays to a much higher floor than
# the casual majority -- this is what lets a small MTU base sustain the orders/user/month
# figure below despite most signups churning fast (mirrors how Zomato/Swiggy MTU is a small
# fraction of lifetime installs). The 18%/82% split and the elevated floor are not
# individually sourced; the target they are tuned to hit (orders per MTU per month) is.
POWER_USER_SHARE = 0.02
POWER_USER_FLOOR = 0.97
# MODELING CHOICE: power users also convert higher per session (saved address/payment,
# familiar reorder flow) -- this multiplier on the two checkout-stage probabilities, plus
# the high floor above, is what lets a ~2% super-user segment reproduce the sourced
# orders/MTU/month figure without the whole 8,000-user cohort behaving as daily-actives
# (which would blow past the sourced D1/D7/D30 retention band).
POWER_USER_CHECKOUT_MULTIPLIER = 2.6

# ---------------------------------------------------------------------------
# Funnel stage-to-stage conversion (probability of advancing, given the prior stage
# happened, on a day the user opens the app):
#   app_open -> browse                 0.80  MODELING CHOICE (most opens lead to browsing)
#   browse -> view_restaurant          0.70  MODELING CHOICE
#   view_restaurant -> add_to_cart     0.50  MODELING CHOICE
#   add_to_cart -> checkout_start      0.30  Baymard Institute, "50 Cart Abandonment Rate
#                                             Statistics 2026" (baymard.com/lists/cart-
#                                             abandonment-rate): ~70.2% average documented
#                                             cart-abandonment rate -> ~30% proceed to checkout.
#   checkout_start -> order_placed     0.65  Aggregated ecommerce checkout-completion
#                                             benchmark reporting, ~60-70% (chatboq.com
#                                             "Ecommerce Funnel Benchmarks 2026"; optimonk.com
#                                             "2026 Industry Conversion Rate Benchmarks").
# Net app_open -> order_placed implied here is ~5.5%, which sits close to the published
# Food & Beverage vertical session->purchase conversion rate of 6.02% (optimonk.com /
# triplewhale.com ecommerce industry benchmarks 2026) used here only as a sanity check,
# since that figure is a web-session metric, not an app-open metric.
STAGE_P = {
    "app_open_to_browse": 0.80,
    "browse_to_view_restaurant": 0.70,
    "view_restaurant_to_add_to_cart": 0.50,
    "add_to_cart_to_checkout_start": 0.30,
    "checkout_start_to_order_placed": 0.65,
}
FUNNEL_STAGES = [
    "app_open", "browse", "view_restaurant", "add_to_cart", "checkout_start", "order_placed",
]

# ---------------------------------------------------------------------------
# Order value (AOV). Swiggy food-delivery AOV was Rs 416 (FY23) rising to Rs 428 (FY24);
# Zomato food-delivery AOV ~Rs 425 over the same period. Source: Swiggy investor
# filings/DRHP as reported by IndMoney "Swiggy vs Zomato FY25 Results"
# (indmoney.com/blog/stocks/swiggy-vs-zomato-fy25) and Feedough "Zomato Statistics 2026"
# (feedough.com/zomato-statistics-facts-user-counts). We center the synthetic order-value
# distribution on this real food-delivery AOV; the wider Rs 380-660 band referenced in the
# project brief spans food delivery through quick-commerce (Blinkit Rs 613-665, Instamart
# Rs 527, same sources) and is used here only as the outer clip range, not the mean.
AOV_MEAN = 425.0
AOV_SIGMA = 0.32  # lognormal shape -> most orders land Rs 250-650
AOV_CLIP = (120.0, 1400.0)

# ---------------------------------------------------------------------------
# Orders per active (transacting) user per month. Zomato reported 20.3M monthly
# transacting users (MTU) placing an average of 3.6 orders/user in Q1 FY25. Source:
# Zomato Investor Presentation, May 2024 (b.zmtcdn.com/investor-relations/
# Zomato_overview_May-24.pdf), as reported by Business Standard / StartupTalky coverage of
# the Q1 FY25 print. This is the real, sourced figure we calibrate to -- it is lower than
# the ~4.5 orders/month/user figure floated in the original brief, and we use the actual
# reported number rather than force-fitting the brief's placeholder.
TARGET_ORDERS_PER_MTU_MONTH = (3.6, 4.5)  # acceptable calibration band


def make_users(n=N_USERS, seed=42) -> pd.DataFrame:
    r = np.random.default_rng(seed)
    signup_offset_days = r.integers(0, (SIGNUP_END - SIGNUP_START).days + 1, size=n)
    signup_date = SIGNUP_START + pd.to_timedelta(signup_offset_days, unit="D")
    city_tier = r.choice(CITY_TIERS, size=n, p=CITY_WEIGHTS)
    is_power_user = r.random(n) < POWER_USER_SHARE
    platform = r.choice(["iOS", "Android"], size=n, p=[0.35, 0.65])
    acquisition_channel = r.choice(
        ["organic", "paid_search", "social", "referral", "in_app_ads"],
        size=n, p=[0.30, 0.25, 0.20, 0.15, 0.10],
    )
    users = pd.DataFrame({
        "user_id": [f"U{100000+i}" for i in range(n)],
        "signup_date": signup_date,
        "city_tier": city_tier,
        "platform": platform,
        "acquisition_channel": acquisition_channel,
        "is_power_user": is_power_user,
    })
    return users


def _retention_curve(days_since_signup: np.ndarray, floor: np.ndarray) -> np.ndarray:
    """Fits a decaying curve through (1, D1), (7, D7), (30, D30) then floors it."""
    t = np.clip(days_since_signup, 1, None).astype(float)
    log_t = np.log(t)
    x = np.array([np.log(1), np.log(7), np.log(30)])
    y = np.log([D1_RETENTION, D7_RETENTION, D30_RETENTION])
    a, b = np.polyfit(x, y, 1)  # log(R) = a*log(t) + b
    r = np.exp(a * log_t + b)
    return np.maximum(r, floor)


def make_funnel_events(users: pd.DataFrame, seed=7) -> tuple[pd.DataFrame, pd.DataFrame]:
    r = np.random.default_rng(seed)
    rows = []
    base_floor = np.where(users["is_power_user"].values, POWER_USER_FLOOR, LONG_RUN_FLOOR)

    for idx, u in users.iterrows():
        max_day = (ANALYSIS_END - u["signup_date"]).days
        if max_day < 1:
            continue
        days = np.arange(1, max_day + 1)
        p_active = _retention_curve(days, base_floor[idx])
        active_mask = r.random(len(days)) < p_active
        active_days = days[active_mask]
        if len(active_days) == 0:
            continue

        p_second_open = 0.55 if u["is_power_user"] else 0.10
        p_chain_base = [
            STAGE_P["app_open_to_browse"],
            STAGE_P["browse_to_view_restaurant"],
            STAGE_P["view_restaurant_to_add_to_cart"],
            STAGE_P["add_to_cart_to_checkout_start"],
            STAGE_P["checkout_start_to_order_placed"],
        ]
        if u["is_power_user"]:
            p_chain_base = p_chain_base[:3] + [
                min(0.95, p_chain_base[3] * POWER_USER_CHECKOUT_MULTIPLIER),
                min(0.95, p_chain_base[4] * POWER_USER_CHECKOUT_MULTIPLIER),
            ]

        for d in active_days:
            event_date = u["signup_date"] + pd.Timedelta(days=int(d))
            n_opens = 1 if r.random() > p_second_open else 2
            for _ in range(n_opens):
                session_id = f"S{r.integers(0, 10**12)}"
                ts = event_date + pd.Timedelta(
                    hours=int(r.integers(8, 23)), minutes=int(r.integers(0, 60))
                )
                stage_reached = 0  # index into FUNNEL_STAGES
                for p in p_chain_base:
                    if r.random() < p:
                        stage_reached += 1
                    else:
                        break
                for s in range(stage_reached + 1):
                    rows.append((
                        session_id, u["user_id"], ts + pd.Timedelta(seconds=s * 20),
                        FUNNEL_STAGES[s], s,
                    ))

    events = pd.DataFrame(rows, columns=["session_id", "user_id", "event_ts", "stage", "stage_order"])

    order_sessions = events[events["stage"] == "order_placed"][["session_id", "user_id", "event_ts"]].copy()
    order_sessions["order_value"] = np.clip(
        r.lognormal(mean=np.log(AOV_MEAN) - (AOV_SIGMA ** 2) / 2, sigma=AOV_SIGMA, size=len(order_sessions)),
        *AOV_CLIP,
    ).round(2)
    order_sessions = order_sessions.rename(columns={"event_ts": "order_ts"})
    order_sessions["order_id"] = [f"O{100000+i}" for i in range(len(order_sessions))]

    return events, order_sessions


# ---------------------------------------------------------------------------
# A/B test: control = existing multi-step checkout, treatment = simplified (fewer fields /
# single page) checkout. Baymard Institute's checkout-usability research finds the average
# large e-commerce site can lift checkout conversion materially (their commonly cited
# headline figure is up to ~35% relatively) purely by fixing checkout usability issues, one
# of which is unnecessary friction/steps (Baymard "Checkout Usability" research, summarized
# via VWO "Q&A with Baymard About Checkout Optimization", vwo.com/blog/christian-holst-
# about-checkout-optimization). We deliberately simulate a materially smaller, more
# conservative lift than that headline figure for the demo test (documented as a MODELING
# CHOICE, not a sourced number) so the A/B test example is realistic rather than a
# best-case cherry-pick.
AB_CONTROL_RATE = STAGE_P["checkout_start_to_order_placed"]  # 0.65
AB_TREATMENT_RATE = 0.715  # MODELING CHOICE: +6.5pp absolute / ~10% relative lift, conservative vs. Baymard's headline range
AB_START = pd.Timestamp("2024-09-01")
AB_END = pd.Timestamp("2024-09-14")
AB_N_PER_ARM = 5200  # MODELING CHOICE: sized for a well-powered demo test


def make_ab_test(seed=99) -> pd.DataFrame:
    r = np.random.default_rng(seed)
    n = AB_N_PER_ARM
    arm = np.array(["control"] * n + ["treatment"] * n)
    r.shuffle(arm)
    converted = np.where(
        arm == "control",
        r.random(2 * n) < AB_CONTROL_RATE,
        r.random(2 * n) < AB_TREATMENT_RATE,
    )
    ts = AB_START + pd.to_timedelta(
        r.integers(0, (AB_END - AB_START).days, size=2 * n), unit="D"
    )
    return pd.DataFrame({
        "checkout_session_id": [f"AB{100000+i}" for i in range(2 * n)],
        "arm": arm,
        "checkout_start_ts": ts,
        "order_placed": converted,
    })


if __name__ == "__main__":
    users = make_users()
    events, orders = make_funnel_events(users)
    ab = make_ab_test()

    users.to_csv("data/processed/synthetic_users.csv", index=False)
    events.to_csv("data/processed/synthetic_funnel_events.csv", index=False)
    orders.to_csv("data/processed/synthetic_orders.csv", index=False)
    ab.to_csv("data/processed/synthetic_ab_test.csv", index=False)

    print("users:", len(users))
    print("funnel event rows:", len(events))
    print("orders:", len(orders), "AOV mean:", round(orders["order_value"].mean(), 2))

    orders_m = orders.merge(users[["user_id"]], on="user_id")
    orders_m["month"] = orders_m["order_ts"].dt.to_period("M")
    mtu = orders_m.groupby("month")["user_id"].nunique()
    opm = orders_m.groupby("month").size() / mtu
    print("orders per MTU per month by month:\n", opm)

    stage_counts = events.groupby("stage")["session_id"].nunique().reindex(FUNNEL_STAGES)
    print("stage session counts:\n", stage_counts)
    print("overall app_open->order_placed:", round(stage_counts["order_placed"] / stage_counts["app_open"], 4))

    first_open = events[events["stage"] == "app_open"].groupby("user_id")["event_ts"].min()
    all_opens = events[events["stage"] == "app_open"][["user_id", "event_ts"]].merge(
        users[["user_id", "signup_date"]], on="user_id"
    )
    all_opens["day_since_signup"] = (
        all_opens["event_ts"].dt.normalize() - all_opens["signup_date"]
    ).dt.days
    for d in (1, 7, 30):
        eligible = users[users["signup_date"] <= ANALYSIS_END - pd.Timedelta(days=d)]
        active = all_opens[all_opens["day_since_signup"] == d]["user_id"].nunique()
        print(f"D{d} retention: {active}/{len(eligible)} = {active/len(eligible):.3f}")
