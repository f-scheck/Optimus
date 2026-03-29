"""
Geometric-Brownian-style monthly returns for the risky sleeve + cash/bonds.
Produces per-path wealth; scenarios = percentiles across paths at each month.
"""

from __future__ import annotations

import numpy as np


def monthly_equity_log_return(
    mu_annual: float,
    sigma_annual: float,
    z: np.ndarray,
) -> np.ndarray:
    """
    One-period (monthly) log return for equity ~ lognormal matching GBM.
    log(1+R) ~ N((mu - 0.5*sigma^2)*dt, sigma^2*dt), dt = 1/12.
    """
    dt = 1.0 / 12.0
    drift = (mu_annual - 0.5 * sigma_annual**2) * dt
    vol = sigma_annual * np.sqrt(dt)
    return drift + vol * z


def run_monte_carlo(
    initial_amount: float,
    monthly_savings: float,
    expected_return_pa: float,
    volatility_pa: float,
    stock_market_share: float,
    horizon_years: int,
    n_simulations: int = 5000,
    risk_free_rate_pa: float = 0.02,
    random_seed: int | None = None,
    best_percentile: float = 95.0,
    worst_percentile: float = 5.0,
) -> dict:
    """
    Simulate wealth paths with monthly contributions.

    Equity sleeve uses expected_return_pa and volatility_pa.
    Non-equity sleeve earns risk_free_rate_pa with zero volatility.
    """
    if horizon_years < 1:
        raise ValueError("horizon_years must be >= 1")
    if not 0 <= stock_market_share <= 1:
        raise ValueError("stock_market_share must be in [0, 1]")
    if n_simulations < 100:
        raise ValueError("n_simulations must be at least 100")
    if volatility_pa < 0:
        raise ValueError("volatility_pa must be non-negative")

    w_eq = float(stock_market_share)
    w_rf = 1.0 - w_eq
    n_months = int(horizon_years * 12)
    dt = 1.0 / 12.0

    rng = np.random.default_rng(random_seed)
    z = rng.standard_normal(size=(n_simulations, n_months))

    log_eq = monthly_equity_log_return(expected_return_pa, volatility_pa, z)
    r_eq = np.expm1(log_eq)

    r_rf = np.expm1(risk_free_rate_pa * dt)
    r_p = w_eq * r_eq + w_rf * r_rf

    wealth = np.empty((n_simulations, n_months + 1), dtype=np.float64)
    wealth[:, 0] = float(initial_amount)
    for t in range(n_months):
        wealth[:, t + 1] = wealth[:, t] * (1.0 + r_p[:, t]) + float(monthly_savings)

    # Percentiles along paths at each time index
    p_best = np.percentile(wealth, best_percentile, axis=0)
    p_avg = np.mean(wealth, axis=0)
    p_worst = np.percentile(wealth, worst_percentile, axis=0)

    months = list(range(n_months + 1))

    return {
        "months": months,
        "best_case": p_best.tolist(),
        "average_case": p_avg.tolist(),
        "worst_case": p_worst.tolist(),
        "best_percentile": best_percentile,
        "worst_percentile": worst_percentile,
        "n_simulations": n_simulations,
        "n_months": n_months,
    }
