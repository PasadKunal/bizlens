"""Generate a synthetic e-commerce dataset matching the BizLens schema.

Use this when the Brazilian Olist Kaggle dataset is not available locally. It
produces users.csv, events.csv, and orders.csv under data/processed with
realistic cohort-retention and funnel patterns (including a paid-vs-organic
retention gap) so every module has data to run against.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CHANNELS = ["organic", "paid", "referral", "email"]
COUNTRIES = ["BR", "US", "PT", "AR", "MX"]
SEGMENTS = ["consumer", "smb", "enterprise"]


def generate(n_users: int = 5000, seed: int = 42, out_dir: str | Path = "data/processed") -> dict:
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Anchor the dataset to "today" so trailing-window KPIs (DAU/MAU, last-90-day
    # revenue) return live data whenever the demo is run. Signups span the last
    # ~180 days: recent cohorts drive current activity, older cohorts give full
    # 12-week retention curves.
    today = pd.Timestamp.today().normalize()

    # --- users --------------------------------------------------------------
    signup = today - pd.to_timedelta(rng.integers(0, 180, n_users), unit="D")
    channel = rng.choice(CHANNELS, n_users, p=[0.4, 0.3, 0.2, 0.1])
    users = pd.DataFrame(
        {
            "user_id": [f"u{i:06d}" for i in range(n_users)],
            "signup_date": signup,
            "channel": channel,
            "country": rng.choice(COUNTRIES, n_users),
            "segment": rng.choice(SEGMENTS, n_users, p=[0.7, 0.22, 0.08]),
        }
    )

    # --- events (retention) -------------------------------------------------
    # Paid users retain worse than organic — a real, testable pattern.
    base_retention = {"organic": 0.80, "paid": 0.60, "referral": 0.75, "email": 0.70}
    event_rows = []
    for _, u in users.iterrows():
        r = base_retention[u.channel]
        for week in range(12):
            if week == 0 or rng.random() < r ** week:
                n_ev = rng.integers(1, 6)
                for _ in range(n_ev):
                    day = u.signup_date + pd.Timedelta(weeks=week, days=int(rng.integers(0, 7)))
                    if day > today:  # don't emit events in the future
                        continue
                    event_rows.append((u.user_id, day, rng.choice(
                        ["visit", "product_view", "add_to_cart", "checkout", "purchase"],
                        p=[0.4, 0.3, 0.15, 0.09, 0.06])))
    events = pd.DataFrame(event_rows, columns=["user_id", "event_date", "event_name"])

    # --- orders -------------------------------------------------------------
    buyers = events[events.event_name == "purchase"]
    orders = pd.DataFrame(
        {
            "order_id": [f"o{i:07d}" for i in range(len(buyers))],
            "user_id": buyers.user_id.values,
            "order_date": buyers.event_date.values,
            "amount": np.round(rng.gamma(2.0, 60.0, len(buyers)), 2),
        }
    )

    users.to_csv(out_dir / "users.csv", index=False)
    events.to_csv(out_dir / "events.csv", index=False)
    orders.to_csv(out_dir / "orders.csv", index=False)
    return {"users": len(users), "events": len(events), "orders": len(orders)}


if __name__ == "__main__":
    print(generate())
