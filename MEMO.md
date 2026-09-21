# Recommendation Memo: Checkout, Delivery Ops & Growth

**To:** Product & Growth leadership
**From:** Product Analytics
**Re:** Findings from the funnel/cohort/growth/delivery/A-B analysis — what to do next
**Data basis:** real Kaggle order-level delivery data (45,593 orders) + a synthetic
funnel/cohort/growth/A-B layer calibrated to cited Zomato/Swiggy/industry benchmarks — see
`README.md > Data Assumptions` for exactly which numbers are real vs. simulated.

---

## 1. Ship the simplified checkout — highest-confidence recommendation

**Decision: SHIP.**

The single biggest leak in the funnel is `add_to_cart → checkout_start`: a ~68% drop on
new-user sessions, consistent with the ~70% cart-abandonment rate Baymard Institute reports
industry-wide. We simulated an A/B test of a simplified (single-page) checkout against the
existing multi-step flow, targeting exactly this stage:

| | Control (existing) | Treatment (simplified) |
|---|---|---|
| Sessions | 5,200 | 5,200 |
| Checkout → order conversion | 64.04% | **72.62%** |

- Absolute lift: **+8.58 percentage points**
- Relative lift: **+13.4%**
- 95% CI on the lift: **[+6.80pp, +10.36pp]** — excludes zero
- Two-proportion z-test: **z = 9.40, p < 0.0001**; chi-square test agrees (χ² = 88.38 = z²,
  p < 0.0001)

The result is unambiguous both statistically and practically. At the current blended
funnel volume, an 8.6pp lift on checkout-stage conversion applied to a ~30% add-to-cart→
checkout rate compounds into a meaningful uplift in bottom-of-funnel orders with no
offsetting cost identified in this analysis.

**Caveat:** this A/B test is simulated, calibrated conservatively against real UX-research
lift ranges rather than run on live traffic (see Data Assumptions). Before a full rollout,
validate the same checkout redesign with a real, held-out traffic test — the direction and
rough magnitude here should transfer, but the exact numbers should not be treated as
production-validated.

## 2. Traffic and weather are the two biggest measured real delivery-time drivers

This is drawn entirely from the real Kaggle dataset (45,593 orders) — no simulation.

- On-time rate (≤30 min SLA) falls from **92.1%** in Low traffic to **49.4%** in Jam
  traffic. Spearman ρ = 0.42, p < 0.001.
- Sunny-weather on-time rate is **87.5%**; Fog/Cloudy is **~56.2%**. ANOVA F = 608.2,
  p < 0.001.

**Recommendation:** invest in traffic- and weather-aware ETA prediction (rather than a
static promise) and pre-emptive rider surge-staffing on Jam-traffic / Fog-Cloudy days.
Static "30-minute delivery" promises are being broken roughly half the time under Jam
traffic — that's a customer-trust risk independent of any funnel work.

## 3. Festival-day capacity is a real, measured operational gap

Festival-day orders in the real dataset show **0% on-time delivery** (45.5 min average)
against 71.4% on-time on non-festival days. The sample is small (896 of 45,593 orders), so
treat the exact 0% as directional rather than precise — but the direction and magnitude are
large enough to warrant action regardless of the exact number.

**Recommendation:** build a dedicated festival-day staffing/capacity playbook (surge rider
incentives, order-cap or dynamic-ETA messaging, restaurant partner prioritization) rather
than running festival demand through business-as-usual operations.

## 4. Growth: a small power-user segment carries disproportionate weight

The simulated growth layer (calibrated to real Zomato MTU/orders-per-user figures) shows
orders-per-ordering-user climbing from 2.0 to 3.9 across the observed period, landing in
the real, cited 3.6–4.5 orders/MTU/month band — but only because a small (~2%), highly
engaged user segment drives most repeat volume; lifetime repeat-customer rate across the
full simulated base is 26.4%.

**Recommendation:** this pattern (a small core driving disproportionate repeat revenue) is
common in food delivery and directionally plausible, but it is **simulated, not measured**
— no real event-level or repeat-purchase data was available to validate it (see README for
why). Before making retention-investment decisions based on this shape specifically,
validate against real cohort data once event-level tracking exists. What *should* transfer
immediately is the general implication: retention/loyalty investment (subscriptions, saved-
payment friction removal, personalized reorder flows) likely has outsized ROI versus
broad-based acquisition spend, because a small segment is doing most of the repeat-revenue
work.

## Summary of actions, in priority order

1. **Ship simplified checkout** — validate with a real A/B test on live traffic, then roll
   out. Highest confidence, clearest evidence, in this analysis.
2. **Build traffic/weather-aware ETA + surge staffing** — real-data-backed, directly
   addresses a measured customer-trust risk.
3. **Build a festival-day capacity playbook** — real-data-backed, large measured effect on
   a currently small but likely-growing order share.
4. **Investigate loyalty/retention investment for the power-user segment** — directionally
   sound, but explicitly flagged as needing real event-level validation before committing
   material budget.
