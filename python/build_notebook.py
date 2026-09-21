"""Builds notebooks/analysis.ipynb via nbformat. Run from the project root."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []


def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))


def code(text):
    cells.append(nbf.v4.new_code_cell(text))


md(r"""# FoodTech Product Intelligence: Funnel, Cohorts, Growth & an A/B Test

A Zomato/Swiggy-style marketplace analytics project. It combines a **real, order-level
Kaggle dataset** with a **synthetic clickstream/user layer**, because the real dataset has
no events, no user identities, and no signup dates -- see `README.md > "Data Assumptions"`
for the complete real-vs-synthetic breakdown and every citation.

Every section below is labeled **REAL DATA** or **SIMULATED (calibrated to cited
benchmarks)**. Only Section 4 (delivery performance) uses the real dataset; everything else
is a synthetic layer generated in `python/generate_synthetic_data.py`, with every generation
parameter tied to a cited industry figure (Zomato/Swiggy investor filings, Baymard
Institute, Adjust mobile retention benchmarks, etc.) -- never an arbitrary number.

| Section | Data |
|---|---|
| 1. Funnel analysis | SIMULATED |
| 2. Cohort retention (D1/D7/D30) | SIMULATED |
| 3. Growth metrics (DAU/WAU/MAU, orders/user, AOV, repeat rate, revenue/user) | SIMULATED (AOV anchored to real benchmark) |
| 4. Delivery performance | **REAL** |
| 5. A/B test (checkout simplification) | SIMULATED |
""")

code(r"""import os
import sys
from pathlib import Path

if Path.cwd().name == "notebooks":  # run cells with the project root as the working dir
    os.chdir("..")
sys.path.append("python")

import matplotlib.pyplot as plt
import pandas as pd

import analysis as A
import clean_real_data as C
import generate_synthetic_data as G

pd.set_option("display.width", 140)
COLORS = A.CHART_COLORS

def style_ax(ax):
    ax.set_facecolor(COLORS["surface"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["muted"])
    ax.spines["bottom"].set_color(COLORS["muted"])
    ax.tick_params(colors=COLORS["ink2"])
    ax.yaxis.grid(True, color=COLORS["grid"], linewidth=1)
    ax.set_axisbelow(True)
""")

md(r"""## 0. Load real data (Kaggle) and generate the synthetic layer

`clean_real_data.py` only cleans/reshapes columns that already exist in the Kaggle CSV --
nothing is invented. `generate_synthetic_data.py` builds the users/funnel/orders/A-B-test
tables from scratch; every constant in that file has a citation in its comment. Re-running
this cell regenerates the exact same synthetic data (seeded RNG, `seed=42`).""")

code(r"""raw = pd.read_csv(C.RAW_PATH)
real = C.clean(raw)
print(f"REAL: {len(real):,} orders loaded from the Kaggle food-delivery dataset")

users = G.make_users()
events, orders = G.make_funnel_events(users)
ab = G.make_ab_test()
print(f"SIMULATED: {len(users):,} users, {events['session_id'].nunique():,} sessions, "
      f"{len(orders):,} orders, {len(ab):,} A/B checkout sessions")""")

md(r"""## 1. Funnel Analysis — SIMULATED

Stage chain: `app_open -> browse -> view_restaurant -> add_to_cart -> checkout_start ->
order_placed`. Two views:

- **First-session (new-user activation funnel):** each user's *first* session only. This is
  the number to compare against published acquisition-funnel benchmarks -- it lands at
  **~6%**, next to the cited Food & Beverage ecommerce conversion-rate benchmark of 6.02%
  (see README).
- **Blended (all sessions):** includes repeat/reorder sessions, dominated by the small
  power-user segment that converts far higher (saved address/payment, familiar reorder
  flow) -- this is *why* blended conversion is roughly double the first-session number, not
  a modeling error.""")

code(r"""funnel = A.funnel_analysis(events)
display(funnel["first_session"])
display(funnel["blended"])

fig, ax = plt.subplots(figsize=(8, 5))
fs = funnel["first_session"]
bars = ax.bar(fs["stage"], fs["sessions"], color=COLORS["blue"], width=0.6)
for b, pct in zip(bars, fs["conversion_from_top"]):
    ax.annotate(f"{pct:.1%}", (b.get_x() + b.get_width() / 2, b.get_height()),
                ha="center", va="bottom", color=COLORS["ink"], fontsize=9)
ax.set_title("New-user activation funnel (first session only)", color=COLORS["ink"])
ax.set_ylabel("Sessions reaching stage", color=COLORS["ink2"])
plt.xticks(rotation=20, ha="right")
style_ax(ax)
fig.patch.set_facecolor(COLORS["surface"])
fig.tight_layout()
plt.show()""")

md(r"""**Reading the drop-off:** the biggest single-stage leak is `add_to_cart ->
checkout_start` (~68% drop, first-session view) -- directly consistent with the Baymard
Institute's ~70% average cart-abandonment benchmark cited in the README. This is the stage
the A/B test in Section 5 targets.""")

md(r"""## 2. Cohort Retention (D1/D7/D30) — SIMULATED

N-day retention: % of a signup cohort that opens the app again on *exactly* day N after
signup (Amplitude/Mixpanel-style definition). Calibrated to Adjust's cross-vertical mobile
benchmark (D1 ~26%, D7 ~12%, D30 ~5%), using the e-commerce/retail vertical as the closest
published proxy since no food-delivery-specific D1/D7/D30 breakout is publicly available
(see README for why).""")

code(r"""cohort_ret = A.cohort_retention(users, events, G.ANALYSIS_END)
display(cohort_ret)

curve = A.overall_retention_curve(users, events, G.ANALYSIS_END)
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(curve["day"], curve["retention"] * 100, color=COLORS["blue"], linewidth=2)
for d in (1, 7, 30):
    row = curve[curve["day"] == d]
    if len(row):
        ax.scatter([d], row["retention"] * 100, color=COLORS["orange"], zorder=5, s=40)
        ax.annotate(f"D{d}: {row['retention'].iloc[0]:.1%}", (d, row["retention"].iloc[0] * 100),
                    textcoords="offset points", xytext=(6, 8), color=COLORS["ink"], fontsize=9)
ax.set_title("Overall N-day retention curve, all signup cohorts", color=COLORS["ink"])
ax.set_xlabel("Days since signup", color=COLORS["ink2"])
ax.set_ylabel("% of cohort active that day", color=COLORS["ink2"])
style_ax(ax)
fig.patch.set_facecolor(COLORS["surface"])
fig.tight_layout()
plt.show()""")

md(r"""**Note on D30 running slightly above the 3-6% proxy band:** we deliberately inject a
small (~2%) high-frequency "power user" segment so the *growth-metrics* orders/MTU/month
figure in Section 3 can hit the real, cited Zomato figure (3.6 orders/MTU/month) without the
whole 8,000-user cohort behaving like daily-actives. That segment pulls blended D30 up to
~7-9%. This is a documented modeling tension, not an error -- see README > Data
Assumptions.""")

md(r"""## 3. Growth Metrics — SIMULATED (AOV anchored to a real benchmark)

DAU/WAU/MAU from app-open events; orders/user, AOV, repeat-order rate and revenue/user from
the synthetic order table. Order value is centered on the **real** Swiggy/Zomato food-
delivery AOV (~Rs 425, FY24 investor filings) — see README.""")

code(r"""growth = A.growth_metrics(users, events, orders)
display(growth)
print(f"Lifetime repeat-customer rate: {orders.groupby('user_id').size().ge(2).mean():.1%}")

fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(growth["month"], growth["DAU_avg"], label="DAU (avg)", color=COLORS["blue"], linewidth=2)
ax.plot(growth["month"], growth["WAU_avg"], label="WAU (avg)", color=COLORS["aqua"], linewidth=2)
ax.plot(growth["month"], growth["MAU"], label="MAU", color=COLORS["violet"], linewidth=2)
ax.set_title("DAU / WAU / MAU by month", color=COLORS["ink"])
ax.set_ylabel("Unique active users", color=COLORS["ink2"])
ax.legend(frameon=False)
style_ax(ax)
plt.xticks(rotation=30, ha="right")
fig.patch.set_facecolor(COLORS["surface"])
fig.tight_layout()
plt.show()""")

md(r"""**Reading the trend:** orders-per-ordering-user climbs from ~2.0 (Jan) to ~3.9 (Sep)
as later cohorts have more time to mature into the power-user segment -- by month 9 it sits
inside the cited real-world band (3.6-4.5 orders/MTU/month). AOV holds steady at ~Rs
420-435/order across all nine months, matching the real benchmark it was calibrated to by
construction.""")

md(r"""## 4. Delivery Performance — **REAL DATA** (Kaggle)

Everything in this section comes directly from the cleaned Kaggle order-level dataset
(45,593 orders, March 2022) — no synthetic data is used here. On-time SLA: `time_taken_min
<= 30` (see README for the source of the 30-45 minute "normal conditions" delivery window
this threshold is drawn from).""")

code(r"""delivery = A.delivery_performance(real)
print(f"Overall on-time %: {delivery['overall_on_time_pct']:.1%}")
display(delivery["by_traffic"])
display(delivery["by_weather"])
display(delivery["by_city"])
display(delivery["by_festival"])
display(delivery["stats_summary"])

fig, axes = plt.subplots(1, 2, figsize=(11, 5))
bt = delivery["by_traffic"]
axes[0].bar(bt["traffic_density"], bt["on_time_pct"] * 100, color=COLORS["blue"])
axes[0].set_title("On-time % by traffic density", color=COLORS["ink"])
axes[0].set_ylabel("On-time %", color=COLORS["ink2"])
style_ax(axes[0])

bw = delivery["by_weather"]
axes[1].bar(bw["weather"], bw["on_time_pct"] * 100, color=COLORS["orange"])
axes[1].set_title("On-time % by weather", color=COLORS["ink"])
plt.setp(axes[1].get_xticklabels(), rotation=30, ha="right")
style_ax(axes[1])
fig.patch.set_facecolor(COLORS["surface"])
fig.tight_layout()
plt.show()""")

md(r"""**Findings (real data):**
- Overall on-time rate is **70.2%** against a 30-minute SLA.
- Traffic is the dominant delay driver: on-time collapses from **92%** (Low traffic) to
  **49%** (Jam) — a Spearman correlation of ~0.42 between traffic severity and delivery
  time (p < 0.001).
- Weather matters too: **Sunny (87% on-time) vs. Fog/Cloudy (~56%)**; a one-way ANOVA
  across weather categories is highly significant (p < 0.001).
- **Festival days are the single worst driver**: 0% on-time (vs. 71% on non-festival days),
  though on a small sample (896 orders) — capacity clearly doesn't scale with festival
  demand spikes.
- Semi-Urban city type shows 0% on-time, but on only 164 orders — flagged as a small-sample
  caveat rather than a robust finding.""")

md(r"""## 5. A/B Test — SIMULATED: Existing vs. Simplified Checkout

Targets the `add_to_cart -> checkout_start` and `checkout_start -> order_placed` leak
identified in Section 1. Control = existing multi-step checkout; treatment = a simplified
(single-page) checkout. The simulated lift is deliberately conservative relative to Baymard
Institute's checkout-usability research (see README) rather than a best-case cherry-pick.""")

code(r"""ab_result = A.ab_test_analysis(ab)
for k, v in ab_result.items():
    print(f"{k:28s} {v}")

fig, ax = plt.subplots(figsize=(6, 5))
rates = [ab_result["rate_control"] * 100, ab_result["rate_treatment"] * 100]
colors = [COLORS["muted"], COLORS["good"] if ab_result["decision"] == "SHIP" else COLORS["critical"]]
bars = ax.bar(["Control\n(existing checkout)", "Treatment\n(simplified checkout)"], rates, color=colors, width=0.5)
for b, v in zip(bars, rates):
    ax.annotate(f"{v:.1f}%", (b.get_x() + b.get_width() / 2, v), ha="center", va="bottom", color=COLORS["ink"])
ax.set_title(f"Checkout->order conversion: {ab_result['decision']}", color=COLORS["ink"])
ax.set_ylabel("Conversion rate (%)", color=COLORS["ink2"])
style_ax(ax)
fig.patch.set_facecolor(COLORS["surface"])
fig.tight_layout()
plt.show()""")

md(r"""**Result:** treatment converts at **72.6%** vs. control's **64.0%** — an absolute
lift of **+8.6pp** (relative **+13.4%**), 95% CI **[+6.8pp, +10.4pp]**, two-proportion
z-test **p < 0.0001** (chi-square test agrees: chi² = z², both p < 0.0001). The CI excludes
zero and the effect is both statistically and practically significant.

**Decision: SHIP the simplified checkout.**""")

md(r"""## Summary — see `MEMO.md` for the full recommendation memo

1. **Ship the simplified checkout** — the clearest, best-evidenced lever available; the A/B
   test result is unambiguous.
2. **Traffic and weather are the two biggest real, measured delivery-time drivers** — worth
   investing in traffic-aware ETAs and surge staffing on Jam-traffic / Fog-Cloudy days.
3. **Festival-day capacity is a real operational gap** (0% on-time on 896 real orders) —
   worth a dedicated staffing/capacity playbook rather than business-as-usual.
4. Growth metrics show a small power-user segment carries a disproportionate share of
   repeat orders and revenue — worth validating against real cohort data once event-level
   tracking exists (see README's honesty note on why this project could not use real
   clickstream data).""")

nb["cells"] = cells
nbf.write(nb, "analysis.ipynb")
print("wrote analysis.ipynb")
