# Monte Carlo service (Cloud Run)

Stateless FastAPI app: POST JSON inputs, get monthly wealth series for **best** (upper percentile), **average** (mean across paths), and **worst** (lower percentile) scenarios.

## Model (short)

- **Equity sleeve**: GBM-style monthly log returns using your `expected_performance_pa` and `volatility_pa`.
- **Non-equity sleeve**: fixed annual `risk_free_rate_pa`, zero volatility.
- **Blend**: each month `portfolio_return = w_equity * equity_return + (1 - w_equity) * risk_free_monthly`.
- **Contributions**: `monthly_savings_plan_amount` added end of each month after growth.

Percentiles default to **95th** (“best”) and **5th** (“worst”); override via request body.

## Run locally

```bash
cd monte_carlo_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

- Health: `GET http://localhost:8080/health`
- Simulate: `POST http://localhost:8080/simulate`

### Example body

```json
{
  "initial_investment_amount": 25000,
  "monthly_savings_plan_amount": 300,
  "expected_performance_pa": 0.07,
  "volatility_pa": 0.16,
  "portfolio_stock_market_share": 0.7,
  "investment_horizon_years": 25,
  "n_simulations": 8000,
  "risk_free_rate_pa": 0.02
}
```

### Example response (shape)

```json
{
  "months": [0, 1, 2, ...],
  "best_case": [25000.0, ...],
  "average_case": [25000.0, ...],
  "worst_case": [25000.0, ...],
  "best_percentile": 95.0,
  "worst_percentile": 5.0,
  "n_simulations": 8000,
  "n_months": 300
}
```

## Deploy to Google Cloud Run

From this directory (with `gcloud` configured):

```bash
export PROJECT_ID=your-project
export REGION=europe-west1
export SERVICE=optimus-monte-carlo

gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE .

gcloud run deploy $SERVICE \
  --image gcr.io/$PROJECT_ID/$SERVICE \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60 \
  --max-instances 10
```

No authentication is configured in the app; use Cloud Run IAM / VPC if you need to restrict access later.

### Cloud Build: `Dockerfile` not at repo root

Cloud Build often checks out the **whole repository** to `/workspace` and looks for **`/workspace/Dockerfile`**. The service Dockerfile lives in **`monte_carlo_service/`**. The repo root **`cloudbuild.yaml`** builds with:

`docker build -f monte_carlo_service/Dockerfile monte_carlo_service`

In a **Cloud Build trigger**, set configuration to **Cloud Build configuration file** → `cloudbuild.yaml`. Match `_AR_REPOSITORY` and `_IMAGE_NAME` in that file to your Artifact Registry repo and image name (or override substitutions in the trigger).

## Docker (manual)

```bash
docker build -t optimus-mc .
docker run --rm -p 8080:8080 optimus-mc
```
