from conftest import load_service_module


notifications = load_service_module("notification-service", "app.notifier")


def test_route_notification_returns_none_for_regular_approved_payment():
    routed = notifications.route_notification({"txn_id": "txn-1", "final_status": "approved", "high_value": False})

    assert routed is None


def test_route_notification_routes_declined_high_value_to_both_channels():
    routed = notifications.route_notification(
        {
            "txn_id": "txn-2",
            "user_id": "user-1",
            "merchant_id": "merchant-demo",
            "amount": 1200.0,
            "currency": "USD",
            "payment_type": "credit",
            "trace_id": "trace-123",
            "final_status": "declined",
            "decision_reason": "High-risk IP reputation",
            "high_value": True,
        }
    )

    assert routed["channels"] == ["email", "slack"]
    assert routed["template"] == "payment-declined"
    assert routed["severity"] == "critical"
    assert routed["status"] == "delivered"
