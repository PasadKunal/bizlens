"""Transform the real Brazilian Olist dataset into the BizLens schema.

The `Olist e-commerce dataset <https://www.kaggle.com/olistbr/brazilian-ecommerce>`_
is a set of normalised transactional CSVs. This loader maps them onto the three
tables BizLens analyses — ``users``, ``events``, ``orders`` — so the real data
flows through the exact same ETL, analytics, and RLS paths as the synthetic set.

Mapping
-------
* **users**  <- customers, keyed by ``customer_unique_id``. ``signup_date`` is
  the customer's first order; ``country`` holds the Brazilian state (the geo
  scope used by RLS); ``segment`` is a spend tercile; Olist has no acquisition
  channel, so ``channel`` is ``unknown``.
* **events** <- order lifecycle timestamps: ``purchase`` (order placed),
  ``checkout`` (approved), ``delivered`` (delivered to customer).
* **orders** <- one row per order, ``amount`` summed from payments (falling back
  to item price + freight).

Usage::

    # after downloading the Kaggle CSVs into data/raw/olist/
    python -m bizlens.sql.olist_loader --raw data/raw/olist --out data/processed
    python -m bizlens.sql.etl_pipeline
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

CUSTOMERS = "olist_customers_dataset.csv"
ORDERS = "olist_orders_dataset.csv"
ITEMS = "olist_order_items_dataset.csv"
PAYMENTS = "olist_order_payments_dataset.csv"


def transform(
    customers: pd.DataFrame,
    orders: pd.DataFrame,
    items: pd.DataFrame | None = None,
    payments: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Map raw Olist frames to (users, events, orders) in the BizLens schema."""
    cust = customers[["customer_id", "customer_unique_id", "customer_state"]].copy()

    o = orders.copy()
    for col in ("order_purchase_timestamp", "order_approved_at", "order_delivered_customer_date"):
        if col in o.columns:
            o[col] = pd.to_datetime(o[col], errors="coerce")
    o = o.merge(cust, on="customer_id", how="left")
    o["user_id"] = o["customer_unique_id"]
    o["country"] = o["customer_state"].str.upper()

    # Order amount: prefer payments, fall back to item price + freight.
    if payments is not None and not payments.empty:
        amt = payments.groupby("order_id")["payment_value"].sum().rename("amount")
    elif items is not None and not items.empty:
        amt = (
            (items["price"] + items["freight_value"])
            .groupby(items["order_id"]).sum().rename("amount")
        )
    else:
        amt = None
    o = o.merge(amt, on="order_id", how="left") if amt is not None else o.assign(amount=0.0)

    # --- users --------------------------------------------------------------
    users = (
        o.sort_values("order_purchase_timestamp")
        .groupby("user_id")
        .agg(
            signup_date=("order_purchase_timestamp", "min"),
            country=("country", "first"),
            total_spend=("amount", "sum"),
        )
        .reset_index()
    )
    users["channel"] = "unknown"
    users["segment"] = pd.qcut(
        users["total_spend"].rank(method="first"),
        q=3,
        labels=["consumer", "smb", "enterprise"],
    ).astype("object")
    users = users[["user_id", "signup_date", "channel", "country", "segment"]]

    # --- events -------------------------------------------------------------
    lifecycle = {
        "order_purchase_timestamp": "purchase",
        "order_approved_at": "checkout",
        "order_delivered_customer_date": "delivered",
    }
    frames = []
    for col, name in lifecycle.items():
        if col in o.columns:
            part = o[["user_id", col]].dropna().rename(columns={col: "event_date"})
            part["event_name"] = name
            frames.append(part)
    events = pd.concat(frames, ignore_index=True)
    events["event_date"] = pd.to_datetime(events["event_date"], errors="coerce")
    events = events.dropna(subset=["event_date", "user_id"])[["user_id", "event_date", "event_name"]]

    # --- orders -------------------------------------------------------------
    orders_out = (
        o[["order_id", "user_id", "order_purchase_timestamp", "amount"]]
        .rename(columns={"order_purchase_timestamp": "order_date"})
        .dropna(subset=["order_date"])
    )
    orders_out["amount"] = orders_out["amount"].fillna(0.0).round(2)

    return users, events, orders_out


def run(raw_dir: str | Path = "data/raw/olist", out_dir: str | Path = "data/processed") -> dict:
    """Read the Olist CSVs from ``raw_dir`` and write BizLens CSVs to ``out_dir``."""
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    customers = pd.read_csv(raw_dir / CUSTOMERS)
    orders = pd.read_csv(raw_dir / ORDERS)
    items = pd.read_csv(raw_dir / ITEMS) if (raw_dir / ITEMS).exists() else None
    payments = pd.read_csv(raw_dir / PAYMENTS) if (raw_dir / PAYMENTS).exists() else None

    users, events, orders_out = transform(customers, orders, items, payments)
    users.to_csv(out_dir / "users.csv", index=False)
    events.to_csv(out_dir / "events.csv", index=False)
    orders_out.to_csv(out_dir / "orders.csv", index=False)
    counts = {"users": len(users), "events": len(events), "orders": len(orders_out)}
    logger.info("olist transform complete: %s", counts)
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Transform Olist CSVs to BizLens schema.")
    parser.add_argument("--raw", default="data/raw/olist")
    parser.add_argument("--out", default="data/processed")
    args = parser.parse_args()
    print(run(args.raw, args.out))
