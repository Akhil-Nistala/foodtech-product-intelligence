"""
End-to-end pipeline: clean real data -> generate synthetic data -> run all five analyses
-> write output/tables/*.csv and output/charts/*.png.

Run from the project root: `python python/run_pipeline.py`
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import analysis as A
import clean_real_data as C
import generate_synthetic_data as G

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


def main():
    print("== 1. clean real data ==")
    raw = pd.read_csv(C.RAW_PATH)
    real = C.clean(raw)
    real.to_csv(C.OUT_PATH, index=False)

    print("== 2. generate synthetic data ==")
    users = G.make_users()
    events, orders = G.make_funnel_events(users)
    ab = G.make_ab_test()
    users.to_csv("data/processed/synthetic_users.csv", index=False)
    events.to_csv("data/processed/synthetic_funnel_events.csv", index=False)
    orders.to_csv("data/processed/synthetic_orders.csv", index=False)
    ab.to_csv("data/processed/synthetic_ab_test.csv", index=False)

    print("== 3. funnel analysis (synthetic) ==")
    funnel = A.funnel_analysis(events)
    funnel["first_session"].to_csv("output/tables/funnel_first_session.csv", index=False)
    funnel["blended"].to_csv("output/tables/funnel_blended_all_sessions.csv", index=False)

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
    fig.savefig("output/charts/funnel_first_session.png", dpi=150)
    plt.close(fig)

    print("== 4. cohort retention (synthetic) ==")
    cohort_ret = A.cohort_retention(users, events, G.ANALYSIS_END)
    cohort_ret.to_csv("output/tables/cohort_retention_by_month.csv", index=False)
    curve = A.overall_retention_curve(users, events, G.ANALYSIS_END)
    curve.to_csv("output/tables/overall_retention_curve.csv", index=False)

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
    fig.savefig("output/charts/retention_curve.png", dpi=150)
    plt.close(fig)

    print("== 5. growth metrics (synthetic) ==")
    growth = A.growth_metrics(users, events, orders)
    growth.to_csv("output/tables/growth_metrics_monthly.csv", index=False)

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
    fig.savefig("output/charts/dau_wau_mau.png", dpi=150)
    plt.close(fig)

    print("== 6. delivery performance (real data) ==")
    delivery = A.delivery_performance(real)
    delivery["by_traffic"].to_csv("output/tables/delivery_by_traffic.csv", index=False)
    delivery["by_weather"].to_csv("output/tables/delivery_by_weather.csv", index=False)
    delivery["by_city"].to_csv("output/tables/delivery_by_city.csv", index=False)
    delivery["by_festival"].to_csv("output/tables/delivery_by_festival.csv", index=False)
    delivery["stats_summary"].to_csv("output/tables/delivery_stats_summary.csv", index=False)
    with open("output/tables/delivery_overall_on_time.txt", "w") as f:
        f.write(f"overall_on_time_pct={delivery['overall_on_time_pct']:.4f}\n")

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
    fig.savefig("output/charts/delivery_performance.png", dpi=150)
    plt.close(fig)

    print("== 7. A/B test (synthetic) ==")
    ab_result = A.ab_test_analysis(ab)
    pd.DataFrame([ab_result]).to_csv("output/tables/ab_test_result.csv", index=False)

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
    fig.savefig("output/charts/ab_test.png", dpi=150)
    plt.close(fig)

    print("\nDONE. Key numbers:")
    print("  real on-time %:", round(delivery["overall_on_time_pct"] * 100, 1))
    print("  funnel first-session app_open->order_placed:",
          round(funnel["first_session"].iloc[-1]["conversion_from_top"] * 100, 2), "%")
    print("  last-month orders/ordering-user:", round(growth.iloc[-1]["orders_per_ordering_user"], 2))
    print("  A/B decision:", ab_result["decision"], "p =", round(ab_result["p_value_ztest"], 5))


if __name__ == "__main__":
    main()
