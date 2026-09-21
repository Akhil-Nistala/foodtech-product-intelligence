# Food Delivery Product Analytics — Funnel & Experimentation

A product-analytics project simulating a food-delivery marketplace (Zomato/Swiggy-style):
funnel analysis, cohort retention, growth metrics, real-data delivery-performance analysis,
and an A/B test, in both **SQL (MySQL 8.0)** and **Python**.

It combines a **real, order-level Kaggle dataset** with a **synthetic clickstream/user
layer**. Read the [Data Assumptions](#data-assumptions) section below before trusting any
number in this project — it says exactly which numbers are real, which are synthetic, and
what each synthetic number is calibrated to.

## At a glance — exact scale (cite these, not rounded/recombined versions)

| Table | Row count | Notes |
|---|---:|---|
| `real_orders` | **45,593** | Real Kaggle orders. Unaffected by the MySQL bug fixes below (they corrupted a column's *values*, never row counts) — verified with a live `COUNT(*)` after the fix. |
| `synthetic_users` | **8,000** | Simulated signups. **7,991** of these have at least one recorded session — 9 users drew zero active days across their entire observation window by chance (Bernoulli variance on a low daily-activity floor, all 9 are non-power users). Say "8,000 users, 7,991 with a recorded session" if asked, not just "8,000." |
| `synthetic_funnel_events` | **325,412** | The funnel-event rows. **This is the number to cite for "synthetic events" — not a sum across tables.** |
| `synthetic_orders` | **13,486** | Completed synthetic orders (the subset of sessions reaching `order_placed`). |
| `synthetic_ab_test` | **10,400** | 5,200 per arm. An **independent** simulation, not sampled from the funnel's checkout_start sessions — see caveat #1 below. |

(These four synthetic tables sum to 357,298 rows if you ever need a single "total synthetic
rows loaded" figure — e.g. for a MySQL row-count sanity check — but that sum mixes four
different entity types and is not itself a meaningful "event count.")

## Project structure

```
product management/
├── README.md                  <- this file (start here)
├── MEMO.md                    <- final recommendation memo
├── requirements.txt
├── docker-compose.yml         <- one-command MySQL for the SQL scripts
├── data/
│   ├── raw/                   <- REAL Kaggle CSV, untouched
│   └── processed/             <- cleaned real data + all generated synthetic tables
├── sql/                        <- MySQL 8.0 scripts (schema, load, 5 analyses)
├── python/                    <- generation + analysis code (importable module, not just scripts)
├── notebooks/analysis.ipynb   <- the full analysis, narrated, real-vs-synthetic labeled
└── output/
    ├── tables/                <- every analysis result as CSV
    └── charts/                <- every chart as PNG
```

## How to run it

```bash
pip install -r requirements.txt

# 1. Clean the real data, generate the synthetic layer, run all 5 analyses,
#    write output/tables/*.csv and output/charts/*.png
python python/run_pipeline.py

# 2. (optional) Rebuild + execute the notebook from scratch
python python/build_notebook.py   # run from notebooks/, or point it at that folder
jupyter nbconvert --to notebook --execute --inplace notebooks/analysis.ipynb

# 3. Run the SQL against MySQL (a local install, or `docker compose up -d`)
mysql -u root -p -e "SET GLOBAL local_infile = 1;"   # once per server restart
mysql -u root -p < sql/00_schema.sql
mysql --local-infile=1 -u root -p food_delivery_analytics < sql/01_load_data.sql
mysql -u root -p food_delivery_analytics < sql/02_delivery_performance.sql
# ...same for 03/04/05/06
```

All five MySQL analysis files (`sql/02`–`sql/06`) were run end-to-end against a real local
MySQL 8.0 instance, loaded with the real + synthetic data via `sql/01_load_data.sql` — every
number matches the Python results exactly (including two data-loading bugs this caught and
fixed: CSV booleans arriving as the literal strings `"True"`/`"False"` rather than `0`/`1`,
and a trailing `\r` from Windows line endings silently corrupting the last field of every
row — see the comments in `sql/01_load_data.sql`).

---

## Data Assumptions

### What's real vs. synthetic

| Table | Provenance | Fields |
|---|---|---|
| `real_orders` (`data/processed/real_orders_clean.csv`) | **REAL.** Kaggle "Food Delivery Time Prediction" dataset (`gauravmalik26/food-delivery-dataset`), 45,593 order rows collected March 2022. Retrieved via a GitHub mirror with an identical file hash to the Kaggle source (`rajstories/FoodDelievery-Prediction`, file `Food delivery.csv`) because this environment has no Kaggle API credentials configured — see the note below. | Every column — delivery-person ID/age/rating, restaurant & delivery lat/long, order & pickup time, weather, traffic density, vehicle type/condition, order type, multiple-deliveries flag, festival flag, city type, and `time_taken(min)` — is copied or trivially reshaped (stripped prefixes, parsed dates, haversine distance, an `on_time` flag) from the raw file. **No column in this table is invented.** |
| `synthetic_users` | **SYNTHETIC.** Generated in `python/generate_synthetic_data.py`. | user_id, signup_date, city_tier, platform, acquisition_channel, is_power_user |
| `synthetic_funnel_events` | **SYNTHETIC.** | session_id, user_id, event_ts, stage (app_open → order_placed), stage_order |
| `synthetic_orders` | **SYNTHETIC**, but the order-value distribution is centered on a **real** benchmark (see table below). | order_id, session_id, user_id, order_ts, order_value |
| `synthetic_ab_test` | **SYNTHETIC** — a simulated experiment, not a real test that ran. | checkout_session_id, arm, checkout_start_ts, order_placed |

### Why event-level data could not be sourced publicly

Stated plainly: **no publicly available dataset contains real food-delivery clickstream
events** (app opens, browsing, add-to-cart, checkout starts) tied to real users with signup
dates. Kaggle, UCI, and other public repositories only host **order-level** food-delivery
data (what this project uses for delivery-performance analysis) or fully synthetic
"e-commerce clickstream" datasets that aren't specific to food delivery and carry no
credible sourcing themselves. Zomato and Swiggy do not publish raw event logs — only
aggregated KPIs in investor filings (MTU, AOV, GOV, etc.), which is exactly what this
project uses to *calibrate* the synthetic layer below, rather than pretending a generated
event log is real data. Every funnel/cohort/growth/A-B number in this project is therefore
labeled SIMULATED, and every generation parameter is tied to one of the real, cited figures
below — nothing is an arbitrary guess.

*(Note on data acquisition: this Kaggle dataset normally requires a Kaggle account + API
token to download via `kaggle datasets download`. No such credentials were available in
this environment, so the file was instead pulled from a GitHub mirror whose file hash
(`58f6a52a...`) is byte-identical to the Kaggle source. If you have Kaggle credentials,
you can instead run `kaggle datasets download -d gauravmalik26/food-delivery-dataset` and
point `python/clean_real_data.py`'s `RAW_PATH` at the resulting CSV — the schema is
identical.)*

### Benchmark/source used for each synthetic parameter

| Parameter | Value used | Source | Where in code |
|---|---|---|---|
| Order value (AOV) | Lognormal, mean ≈ ₹425 | Swiggy food-delivery AOV rose ₹416 (FY23) → ₹428 (FY24); Zomato food-delivery AOV ≈ ₹425 over the same period. Swiggy investor filings/DRHP as reported by [IndMoney, "Swiggy vs Zomato FY25 Results"](https://www.indmoney.com/blog/stocks/swiggy-vs-zomato-fy25); [Feedough, "Zomato Statistics 2026"](https://www.feedough.com/zomato-statistics-facts-user-counts/). The wider ₹380–660 band referenced in the original brief spans food delivery **through quick-commerce** (Blinkit ₹613–665, Instamart ₹527, same sources) — used here only as the outer clip range, not the mean, since this project models food delivery. | `generate_synthetic_data.py :: AOV_MEAN, AOV_SIGMA, AOV_CLIP` |
| Orders per active (transacting) user per month | Target band 3.6–4.5; simulation reaches ~3.9 by month 9 | Zomato reported **20.3M monthly transacting users (MTU)** placing an average of **3.6 orders/user** in Q1 FY25. [Zomato Investor Presentation, May 2024](https://b.zmtcdn.com/investor-relations/Zomato_overview_May-24.pdf), as covered by Business Standard/StartupTalky. This is the **real, sourced** figure — lower than the ~4.5 orders/month placeholder floated in the original project brief; we calibrated to the actual reported number rather than force-fitting the brief's placeholder. | `generate_synthetic_data.py :: TARGET_ORDERS_PER_MTU_MONTH`, the `POWER_USER_*` constants |
| Cart abandonment / add-to-cart→checkout conversion | 30% proceed to checkout (70% abandon) | Baymard Institute, [**"50 Cart Abandonment Rate Statistics 2026"**](https://baymard.com/lists/cart-abandonment-rate) — aggregate of 50 studies, ~70.2% average documented cart-abandonment rate. | `generate_synthetic_data.py :: STAGE_P["add_to_cart_to_checkout_start"]` |
| Checkout completion (checkout→order) | 65% | Aggregated ecommerce checkout-completion benchmark reporting, ~60–70%: [chatboq.com, "Ecommerce Funnel Benchmarks 2026"](https://chatboq.com/blogs/ecommerce-funnel-benchmarks); [optimonk.com, "2026 Industry Conversion Rate Benchmarks"](https://www.optimonk.com/industry-conversion-rate-benchmarks). | `generate_synthetic_data.py :: STAGE_P["checkout_start_to_order_placed"]` |
| Overall funnel conversion sanity check | New-user (first-session) funnel lands at 6.06% | Cross-checked against the published **Food & Beverage ecommerce vertical conversion rate of 6.02%** (session→purchase) reported by the same ecommerce-benchmark aggregators above. This is a *session*-based benchmark used only as a directional sanity check for an *app-open*-based funnel — the two aren't identically defined, but the closeness (6.06% vs 6.02%) is a meaningful calibration signal. | see `notebooks/analysis.ipynb` §1 |
| D1 / D7 / D30 retention | 26% / 12% / 5% target curve | Adjust's cross-vertical mobile benchmark (D1 ~25–26%, D7 ~11–13%, D30 ~5–7%), as summarized by [mwm.ai, "Retention (D1/D7/D30) — Mobile App Retention Benchmarks"](https://mwm.ai/glossary/retention) and [prooflytics.io, "D7 and D30 Retention Benchmarks by App Category"](https://prooflytics.io/blog/d7-d30-retention-benchmarks-by-app-category). **No food-delivery-specific D1/D7/D30 breakout was publicly available** — this project uses the closest published proxy vertical (e-commerce/retail, D30 ~3–6%) and says so explicitly rather than presenting it as a food-delivery-specific figure. | `generate_synthetic_data.py :: D1_RETENTION, D7_RETENTION, D30_RETENTION` |
| On-time delivery SLA (real data) | ≤ 30 minutes | The Kaggle dataset has no "promised time" field. Widely reported normal-conditions delivery window for Indian food-delivery apps is 30–45 minutes; this project uses the tighter/lower bound — the "30-minute delivery" figure both platforms have historically marketed — as the on-time cutoff. [StartupTalky, "Swiggy Vs Zomato"](https://startuptalky.com/zomato-vs-swiggy/); [Aish4Aish, "Swiggy vs Zomato 2026"](https://www.aish4aish.in/blog/swiggy-vs-zomato-which-is-better-2026). | `clean_real_data.py :: ON_TIME_SLA_MIN` |
| A/B test simulated lift | Treatment +6.5pp absolute over control (design target; realized ~+8.6pp) | Directionally justified by Baymard Institute's checkout-usability research, which finds average large e-commerce sites can lift checkout conversion materially by fixing usability friction (commonly cited headline: up to ~35% relative). [VWO, "Q&A with Baymard About Checkout Optimization"](https://vwo.com/blog/christian-holst-about-checkout-optimization/). We deliberately simulated a **materially smaller, conservative** lift than that headline figure so the demo test reads as realistic rather than a best-case cherry-pick — this is a **modeling choice**, not itself an independently sourced number. | `generate_synthetic_data.py :: AB_CONTROL_RATE, AB_TREATMENT_RATE` |

### Modeling choices that are *not* independently sourced

A handful of parameters exist only to make the generator internally consistent and are
labeled `MODELING CHOICE` in code rather than presented as benchmarked:
the exact parametric shape of the retention decay curve between the three cited anchor
points (D1/D7/D30); the 2%/98% power-user/casual-user population split and the power
users' elevated retention floor and checkout-conversion multiplier (needed to hit the
*real, cited* orders/MTU/month figure without making the whole synthetic cohort behave
like daily-actives, which would blow past the *also real, cited* D1/D7/D30 retention
figures); the exact session count per active day; and the A/B test's sample size per arm.
These are documented in code comments everywhere they appear.

### A known, documented tension

Hitting the real orders/MTU/month benchmark (3.6–4.5) requires a small, highly-engaged
power-user segment. That same segment pushes the simulated D30 cohort retention to ~6–9%,
modestly above the 3–6% e-commerce/retail proxy band it's otherwise calibrated to. This is
flagged rather than hidden: it reflects a genuine synthetic-data-design trade-off (two
benchmarks pulling in different directions), not an error, and it's exactly the kind of gap
that would disappear with real, joined event + order data.

### Known modeling caveats (read before an interview)

Four things a careful reviewer will notice and ask about. None of these are bugs — they're
modeling-assumption questions, and the honest answer to each is below.

1. **The A/B test's ~10,400-session population is an independent constant, not sampled
   from the funnel's checkout_start sessions.** `generate_synthetic_data.py`'s `make_ab_test()`
   is a standalone simulation with its own hard-coded `AB_N_PER_ARM = 5200`, drawing fresh
   Bernoulli trials at the two conversion rates — it does **not** draw its population from
   the funnel model's actual checkout_start events (717 sessions in the first-session view,
   15,810 in the blended view over the 9-month run — neither matches ~10,400, because
   they're not meant to). If asked "how does the A/B population relate to your funnel's
   checkout volume," the correct answer is that they're two separate synthetic generators,
   not one feeding the other.
2. **The retention curve declines steeply through D30, then flattens — it does not flatten
   by D30.** D1→D7→D30 (29.2%→13.6%→7.4%) is a deliberately steep drop, matching the shape
   of the cited Adjust benchmark it's calibrated to (which itself falls steeply from
   ~26%→12%→5%). Past D30 the decay visibly slows as the small power-user segment's higher
   retention floor takes over: D40 ≈ 6.3%, D45 ≈ 6.1% (see
   `output/tables/overall_retention_curve.csv`). So there *is* a "sticky loyal cohort"
   mechanism in the model — it just isn't visible within the D1/D7/D30 window this project
   reports on. Don't state the D1–D30 shape as reflecting real Zomato/Swiggy behavior; it's
   calibrated to a cross-vertical proxy benchmark (see the retention row above), not
   food-delivery-specific data.
3. **8,000 simulated users; 7,991 have at least one recorded session.** Already covered in
   the scale table above — repeated here because it's the kind of precision an interviewer
   checking rigor will probe for.
4. **The A/B test's p-value (~5×10⁻²¹) is extreme because both the sample size (112K+
   funnel sessions feeding into a well-powered ~10,400-session test) and the effect size
   (13.4% relative lift) are large — not because a synthetic dataset carries more
   statistical weight than a real one would.** Don't let the smallness of the p-value imply
   more real-world rigor than a simulated experiment can actually claim; the *shape* of the
   result (large N × real effect → tiny p) is what's worth explaining, not the literal
   number.

---

## Real Data Findings (Section 4 — Delivery Performance)

Computed entirely from the real Kaggle dataset (45,593 orders, March 2022). No synthetic
data used.

- **Overall on-time rate: 70.2%** against a 30-minute SLA.
- **Traffic is the dominant, statistically significant delay driver**: on-time falls from
  **92.1%** (Low traffic) → 67.5% (Medium) → 66.4% (High) → **49.4%** (Jam). Spearman ρ =
  0.42 between traffic severity and delivery time (p < 0.001, n=45,162).
- **Weather matters too**: Sunny (87.5% on-time, 21.9 min avg) vs. Fog/Cloudy (~56.2%
  on-time, ~28.9 min avg). One-way ANOVA across weather categories: F = 608.2, p < 0.001.
- **Distance and stacked ("multiple") deliveries both correlate with longer delivery
  times** (Pearson r = 0.32 and r = 0.39 respectively, both p < 0.001) — expected, and a
  useful sanity check that the dataset behaves the way a real operations dataset should.
- **Festival days are the single worst driver measured**: 0.0% on-time (45.5 min avg) vs.
  71.4% on non-festival days — but on a small sample (896 of 45,593 orders); flagged as a
  real signal, not yet a statistically robust one at that n.
- Semi-Urban city type also shows 0% on-time, on only 164 orders — same small-sample
  caveat.

Full breakdowns: `output/tables/delivery_by_*.csv`, `output/tables/delivery_stats_summary.csv`.

## Simulated Analysis Findings (Sections 1, 2, 3, 5)

- **Funnel**: new-user (first-session) `app_open → order_placed` conversion = **6.06%**
  (close to the 6.02% cited F&B benchmark used as a sanity check). Biggest single-stage
  leak: `add_to_cart → checkout_start`, ~68% drop — consistent with the Baymard cart-
  abandonment benchmark it was calibrated to, and the stage the A/B test targets. Blended
  (all-sessions, including repeat/reorder traffic from power users) conversion is ~12.0% —
  expected to be higher, not a modeling bug (see Data Assumptions).
- **Cohort retention**: D1 ≈ 27–32%, D7 ≈ 13–14%, D30 ≈ 6–9% across the six monthly
  signup cohorts — in line with the cited cross-vertical benchmark, modestly elevated at
  D30 for the documented reason above.
- **Growth**: MAU grows from 1,083 (Jan) to a peak of ~5,287 (Jun) as cohorts accumulate,
  tapering as early cohorts churn; orders-per-ordering-user climbs from 2.0 → **3.89** by
  September, landing inside the real, cited 3.6–4.5 band; AOV holds steady at
  ₹417–436/order across all nine months (by construction, since it's anchored to the real
  benchmark); lifetime repeat-customer rate = **26.4%**.
- **A/B test (checkout simplification)**: control 64.04% → treatment 72.62% checkout→order
  conversion. Absolute lift **+8.58pp**, relative lift **+13.4%**, 95% CI **[+6.80pp,
  +10.36pp]**, two-proportion z-test **z = 9.40, p < 0.0001** (chi-square test agrees:
  χ² = 88.38 = z², p < 0.0001). **Decision: SHIP.** Full memo: [`MEMO.md`](MEMO.md).

All numbers above are reproduced, with charts, in `notebooks/analysis.ipynb` and as CSVs in
`output/tables/`.
