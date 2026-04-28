from __future__ import annotations

import math


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes_price(
    spot: float,
    strike: float,
    years: float,
    rate: float,
    vol: float,
    option_type: str,
) -> float:
    if years <= 0 or vol <= 0 or spot <= 0 or strike <= 0:
        return max(0.0, spot - strike) if option_type == "CE" else max(0.0, strike - spot)

    sqrt_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * years) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    discounted_strike = strike * math.exp(-rate * years)

    if option_type == "CE":
        return spot * norm_cdf(d1) - discounted_strike * norm_cdf(d2)
    return discounted_strike * norm_cdf(-d2) - spot * norm_cdf(-d1)


def implied_volatility(
    option_price: float,
    spot: float,
    strike: float,
    years: float,
    rate: float,
    option_type: str,
    low: float = 0.0001,
    high: float = 5.0,
    tolerance: float = 1e-5,
    max_iterations: int = 100,
) -> float | None:
    intrinsic = max(0.0, spot - strike) if option_type == "CE" else max(0.0, strike - spot)
    if option_price < intrinsic or years <= 0:
        return None

    low_price = black_scholes_price(spot, strike, years, rate, low, option_type)
    high_price = black_scholes_price(spot, strike, years, rate, high, option_type)
    if option_price < low_price or option_price > high_price:
        return None

    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        price = black_scholes_price(spot, strike, years, rate, mid, option_type)
        if abs(price - option_price) < tolerance:
            return mid
        if price < option_price:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0

