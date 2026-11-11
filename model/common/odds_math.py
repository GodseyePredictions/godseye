"""Odds maths in Python. A port of src/lib/odds.ts so both sides of the site agree.
All odds are American (-110, +250) unless a name says decimal. Probabilities are 0..1."""


def to_decimal(american: float) -> float:
    if not american or american != american:
        raise ValueError("Invalid American odds")
    return 1 + american / 100 if american > 0 else 1 + 100 / -american


def implied_prob(american: float) -> float:
    return 1 / to_decimal(american)


def fair_probs(american_prices: list[float]) -> list[float]:
    raw = [implied_prob(a) for a in american_prices]
    total = sum(raw)
    return [p / total for p in raw]


def decimal_to_american(d: float) -> int:
    return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))


def fair_american(p: float) -> int:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return decimal_to_american(1 / p)


def expected_value(true_prob: float, american: float) -> float:
    return true_prob * (to_decimal(american) - 1) - (1 - true_prob)


def kelly_stake(true_prob: float, american: float, fraction: float = 0.25) -> float:
    b = to_decimal(american) - 1
    return max(0.0, (true_prob * b - (1 - true_prob)) / b * fraction)


def closing_line_value(bet_american: float, close_american: float) -> float:
    """Change in implied win chance between your price and the close. Positive = you beat the close."""
    return implied_prob(close_american) - implied_prob(bet_american)


def parse_price(text) -> float:
    """Accept American (-110, +250), decimal (1.91) or fractional (10/11) prices; return American."""
    s = str(text).strip().replace("−", "-")
    if "/" in s:
        a, b = s.split("/")
        return float(decimal_to_american(1 + float(a) / float(b)))
    v = float(s)
    if s.startswith(("+", "-")) or abs(v) >= 100:
        if abs(v) < 100:
            raise ValueError("American odds must be at least 100 either side")
        return v
    if v <= 1.0:
        raise ValueError("decimal odds must be above 1.0")
    return float(decimal_to_american(v))
