"""
FastAPI Monte Carlo wealth projection for Cloud Run (no auth).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, model_validator

from app.simulation import run_monte_carlo

app = FastAPI(
    title="Optimus Monte Carlo",
    description="Wealth simulation: best / average / worst case time series",
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


class SimulationResponse(BaseModel):
    months: list[int]
    best_case: list[float]
    average_case: list[float]
    worst_case: list[float]
    best_percentile: float
    worst_percentile: float
    n_simulations: int
    n_months: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/simulate", response_model=SimulationResponse)
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

    return SimulationResponse(**out)
