def format_currency(amount) -> str:
    try:
        return f"₹{float(amount):,.2f}"
    except (TypeError, ValueError):
        return "₹0.00"


def format_liters(liters) -> str:
    try:
        return f"{float(liters):,.2f} L"
    except (TypeError, ValueError):
        return "0.00 L"
