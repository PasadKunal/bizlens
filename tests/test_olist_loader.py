import pandas as pd

from bizlens.sql.olist_loader import transform


def _fixtures():
    customers = pd.DataFrame(
        {
            "customer_id": ["c1", "c2", "c3", "c4"],
            "customer_unique_id": ["u1", "u2", "u3", "u1"],  # u1 has two orders
            "customer_state": ["sp", "rj", "mg", "sp"],
        }
    )
    orders = pd.DataFrame(
        {
            "order_id": ["o1", "o2", "o3", "o4"],
            "customer_id": ["c1", "c2", "c3", "c4"],
            "order_purchase_timestamp": [
                "2018-01-01 10:00", "2018-01-10 09:00", "2018-01-05 12:00", "2018-02-01 08:00",
            ],
            "order_approved_at": [
                "2018-01-01 11:00", "2018-01-10 10:00", "2018-01-05 13:00", "2018-02-01 09:00",
            ],
            "order_delivered_customer_date": [
                "2018-01-05 00:00", "2018-01-14 00:00", None, None,
            ],
        }
    )
    payments = pd.DataFrame(
        {"order_id": ["o1", "o2", "o3", "o4"], "payment_value": [100.0, 50.0, 200.0, 30.0]}
    )
    return customers, orders, payments


def test_users_dedup_and_signup():
    customers, orders, payments = _fixtures()
    users, _, _ = transform(customers, orders, payments=payments)

    assert len(users) == 3  # u1 appears twice but collapses to one user
    u1 = users.set_index("user_id").loc["u1"]
    assert pd.Timestamp(u1["signup_date"]) == pd.Timestamp("2018-01-01 10:00")
    assert u1["country"] == "SP"  # uppercased state
    assert u1["channel"] == "unknown"
    assert set(users["segment"]) <= {"consumer", "smb", "enterprise"}


def test_events_from_lifecycle_timestamps():
    customers, orders, payments = _fixtures()
    _, events, _ = transform(customers, orders, payments=payments)

    assert set(events["event_name"]) == {"purchase", "checkout", "delivered"}
    assert (events["event_name"] == "purchase").sum() == 4   # one per order
    assert (events["event_name"] == "delivered").sum() == 2  # only two delivered


def test_orders_amount_from_payments():
    customers, orders, payments = _fixtures()
    _, _, orders_out = transform(customers, orders, payments=payments)

    assert len(orders_out) == 4
    assert orders_out.set_index("order_id").loc["o1", "amount"] == 100.0


def test_amount_falls_back_to_items_when_no_payments():
    customers, orders, _ = _fixtures()
    items = pd.DataFrame(
        {"order_id": ["o1", "o2", "o3", "o4"],
         "price": [90.0, 40.0, 190.0, 20.0],
         "freight_value": [10.0, 10.0, 10.0, 10.0]}
    )
    _, _, orders_out = transform(customers, orders, items=items, payments=None)
    assert orders_out.set_index("order_id").loc["o1", "amount"] == 100.0
