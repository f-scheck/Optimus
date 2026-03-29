"""
FastAPI Monte Carlo wealth projection for Cloud Run (no auth).
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
