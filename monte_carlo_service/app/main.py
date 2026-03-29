"""
FastAPI Monte Carlo wealth projection for Cloud Run (no auth).
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.simulation import run_monte_carlo


def _add_months(d: date, months: int) -> date:
    """Calendar month offset; clamps day to last day of month when needed."""
    m0 = d.month - 1 + months
    year = d.year + m0 // 12
    month = m0 % 12 + 1
    last = calendar.monthrange(year, month)[1]
    day = min(d.day, last)
    return date(year, month, day)


def _date_to_utc_start_ms(d: date) -> int:
    dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _highstock_series(
    month_indices: list[int],
    best: list[float],
    _average: list[float],
    worst: list[float],
    start: date,
    best_pct: float,
    worst_pct: float,
    initial_amount: float,
    monthly_savings: float,
) -> list[dict]:
    times = [_date_to_utc_start_ms(_add_months(start, m)) for m in month_indices]

    def rows(vals: list[float]) -> list[list]:
        return [[t, round(float(v), 2)] for t, v in zip(times, vals)]

    def rows_arearange(low: list[float], high: list[float]) -> list[list]:
        out: list[list] = []
        for t, lo, hi in zip(times, low, high):
            a, b = (float(lo), float(hi)) if lo <= hi else (float(hi), float(lo))
            out.append([t, round(a, 2), round(b, 2)])
        return out

    # Cumulative cash invested: matches simulation indices (month 0 = initial only).
    invested = [round(float(initial_amount) + float(m) * float(monthly_savings), 2) for m in month_indices]

    return [
        {
            "name": f"Range p{worst_pct:g}–p{best_pct:g} (worst–best)",
            "type": "arearange",
            "fillOpacity": 0.35,
            "lineWidth": 0,
            "data": rows_arearange(worst, best),
        },
        {
            "name": "Total invested (initial + cumulative savings)",
            "type": "line",
            "dashStyle": "ShortDash",
            "data": rows(invested),
        },
    ]

app = FastAPI(
    title="Optimus Monte Carlo",
    description="Wealth simulation: percentile range (arearange) and invested baseline",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Optimus — Portfolio optimization</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: linear-gradient(160deg, #0f172a 0%, #1e293b 45%, #0c4a6e 100%);
      color: #e2e8f0;
    }
    .card {
      text-align: center;
      padding: 2.5rem 2rem;
      max-width: 28rem;
    }
    .logo {
      width: 88px;
      height: 88px;
      margin: 0 auto 1.25rem;
      filter: drop-shadow(0 8px 24px rgba(56, 189, 248, 0.25));
    }
    h1 {
      margin: 0 0 0.35rem;
      font-size: 1.75rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #f8fafc;
    }
    .tagline {
      margin: 0;
      font-size: 1rem;
      line-height: 1.5;
      color: #94a3b8;
    }
    .by {
      display: block;
      margin-top: 0.75rem;
      font-size: 0.875rem;
      color: #38bdf8;
      font-weight: 500;
    }
    .links {
      margin-top: 1.75rem;
      font-size: 0.8125rem;
    }
    .links a {
      color: #7dd3fc;
      text-decoration: none;
    }
    .links a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="card">
    <svg class="logo" viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#38bdf8"/>
          <stop offset="100%" style="stop-color:#0ea5e9"/>
        </linearGradient>
      </defs>
      <circle cx="48" cy="48" r="44" fill="none" stroke="url(#g)" stroke-width="3" opacity="0.35"/>
      <path d="M22 58 L36 44 L50 52 L64 32 L74 38" fill="none" stroke="url(#g)" stroke-width="3.5"
            stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="74" cy="38" r="4" fill="#38bdf8"/>
    </svg>
    <h1>Optimus</h1>
    <p class="tagline">Portfolio optimization repository</p>
    <span class="by">by fscheck</span>
    <p class="links"><a href="/docs">API docs</a> · <a href="/health">health</a></p>
  </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(content=_INDEX_HTML)


class SimulationRequest(BaseModel):
    initial_investment_amount: float = Field(..., ge=0, description="Starting capital")
    monthly_savings_plan_amount: float = Field(..., ge=0, description="Contribution each month")
    expected_performance_pa: float = Field(
        ...,
        description="Expected annual return of the equity sleeve (e.g. 0.07 for 7%)",
    )
    volatility_pa: float = Field(
        ...,
        ge=0,
        description="Annual volatility (std dev of returns) of the equity sleeve",
    )
    portfolio_stock_market_share: float = Field(
        ...,
        ge=0,
        le=1,
        description="Weight in risky equity; remainder in risk-free sleeve",
    )
    investment_horizon_years: int = Field(..., ge=1, le=80)
    n_simulations: int = Field(5000, ge=100, le=100_000)
    risk_free_rate_pa: float = Field(
        0.02,
        ge=0,
        le=0.2,
        description="Annual return of the non-equity sleeve (approx., zero vol)",
    )
    random_seed: int | None = Field(None, description="Optional seed for reproducibility")
    best_percentile: float = Field(95.0, ge=50, lt=100)
    worst_percentile: float = Field(5.0, gt=0, le=50)

    @model_validator(mode="after")
    def check_positive_flow(self):
        if self.initial_investment_amount <= 0 and self.monthly_savings_plan_amount <= 0:
            raise ValueError("At least one of initial_investment_amount or monthly_savings_plan_amount must be > 0")
        return self


class HighstockSeries(BaseModel):
    """Highcharts series: line/area use [x, y]; arearange uses [x, low, high]."""

    model_config = ConfigDict(exclude_none=True)

    name: str
    type: str = "line"
    data: list[list[float | int]]
    dashStyle: str | None = "Solid"
    fillOpacity: float | None = None
    lineWidth: int | None = None


class SimulationChartResponse(BaseModel):
    """
    Drop-in for Highcharts Stock: pass `series` to the chart config.
    Use xAxis: { type: 'datetime' }; timestamps are UTC start-of-day per month from start_date_utc.
    Series order: worst–best (arearange), total invested (line).
    """

    series: list[HighstockSeries]
    x_axis_type: Literal["datetime"] = "datetime"
    time_zone: Literal["UTC"] = "UTC"
    start_date_utc: str
    best_percentile: float
    worst_percentile: float
    n_simulations: int
    n_months: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post(
    "/simulate",
    response_model=SimulationChartResponse,
    response_model_exclude_none=True,
)
def simulate(body: SimulationRequest):
    try:
        out = run_monte_carlo(
            initial_amount=body.initial_investment_amount,
            monthly_savings=body.monthly_savings_plan_amount,
            expected_return_pa=body.expected_performance_pa,
            volatility_pa=body.volatility_pa,
            stock_market_share=body.portfolio_stock_market_share,
            horizon_years=body.investment_horizon_years,
            n_simulations=body.n_simulations,
            risk_free_rate_pa=body.risk_free_rate_pa,
            random_seed=body.random_seed,
            best_percentile=body.best_percentile,
            worst_percentile=body.worst_percentile,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    start = datetime.now(timezone.utc).date()
    series_payload = _highstock_series(
        out["months"],
        out["best_case"],
        out["average_case"],
        out["worst_case"],
        start,
        out["best_percentile"],
        out["worst_percentile"],
        body.initial_investment_amount,
        body.monthly_savings_plan_amount,
    )
    return SimulationChartResponse(
        series=[HighstockSeries(**s) for s in series_payload],
        start_date_utc=start.isoformat(),
        best_percentile=out["best_percentile"],
        worst_percentile=out["worst_percentile"],
        n_simulations=out["n_simulations"],
        n_months=out["n_months"],
    )
