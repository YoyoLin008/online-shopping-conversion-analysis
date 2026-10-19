# GitHub: https://github.com/YoyoLin008/online-shopping-conversion-analysis
# Data: Sakar & Kastro (2018), UCI; doi:10.24432/C5F88Q (CC BY 4.0).
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
raw = pd.read_csv(ROOT / "support/data/online_shoppers_intention.csv",
                  dtype={"Revenue": "boolean", "VisitorType": "string",
                         "Month": "string"})
cols = ["VisitorType", "Month", "Revenue"]
assert raw[cols].notna().all().all(), "Missing analysis fields"
labels = {"New_Visitor": "New", "Returning_Visitor": "Returning"}
assert raw.VisitorType.isin([*labels, "Other"]).all()
# Keep identical feature rows: there is no session ID to prove duplication.
df = raw.loc[raw.VisitorType.isin(labels), cols].copy()
df["visitor"] = pd.Categorical(df.VisitorType.map(labels),
                                categories=["New", "Returning"])
df["purchased"] = df.Revenue.astype("int8")  # Boolean -> 0/1 outcome.
df["Month"] = df.Month.astype("category")
print(f"Read {len(raw):,} sessions; excluded {len(raw)-len(df):,} Other.")

def conversion_summary(frame, by):
    """Return purchase counts, rates and 95% Wilson binomial intervals."""
    s = frame.groupby(by, observed=True).purchased.agg(
        n="size", purchases="sum")
    n, k = s.n, s.purchases
    assert (n > 0).all() and ((k >= 0) & (k <= n)).all()
    p, z = k / n, 1.96
    center = (p + z*z/(2*n)) / (1 + z*z/n)
    half = z * np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return s.assign(rate=p, low=center-half, high=center+half)

summary = conversion_summary(df, "visitor")
monthly = conversion_summary(df, ["Month", "visitor"])
rates = monthly.rate.unstack("visitor")
assert rates.notna().all().all(), "Both groups must occur in each month"
# Give each group the same month weights to check compositional differences.
weights = df.groupby("Month", observed=True).size() / len(df)
summary["adjusted"] = rates.mul(weights, axis=0).sum()

table = summary[["n", "purchases"]].copy()
for col in ["rate", "low", "high", "adjusted"]:
    table[col + "_%"] = 100 * summary[col]
print(table.to_string(float_format=lambda x: f"{x:.2f}"))
gap = 100 * (summary.loc["New"] - summary.loc["Returning"])
print(f"New - Returning: {gap.rate:.2f} pp observed; "
      f"{gap.adjusted:.2f} pp month-standardized.")

# Intervals describe observed rates; diamonds are standardized point estimates.
plt.rcParams.update({"font.family": "serif", "font.size": 11,
                     "font.serif": ["Times New Roman", "DejaVu Serif"]})
fig, ax = plt.subplots(figsize=(7.2, 2.4), layout="constrained")
y = np.arange(len(summary))
errors = 100 * np.vstack([summary.rate-summary.low,
                         summary.high-summary.rate])
ax.errorbar(100*summary.rate, y+0.08, xerr=errors, fmt="o",
            color="black", capsize=4, label="Observed (95% Wilson CI)")
ax.scatter(100*summary.adjusted, y-0.08, marker="D", s=38,
           facecolor="white", edgecolor="black", label="Common month mix")
ax.set(yticks=y, yticklabels=summary.index, xlim=(0, 32),
       ylim=(1.6, -0.5), xlabel="Sessions ending in a purchase (%)")
ax.spines[["top", "right", "left"]].set_visible(False)
ax.grid(axis="x", alpha=0.18)
ax.set_axisbelow(True)
ax.legend(loc="lower left", frameon=False, fontsize=10, ncol=2)
fig.savefig(ROOT / "support/results/conversion_comparison.png", dpi=300)
plt.close(fig)
