# Deploy Monte Carlo API to Cloud Run (Dockerfile in a subfolder)

The FastAPI service lives under **`monte_carlo_service/`**. The **`Dockerfile` is not at the repository root**, so Cloud Build must not use the default `/workspace/Dockerfile`.

## Recommended: root `cloudbuild.yaml`

This repo includes **`cloudbuild.yaml` at the repository root**. It runs:

```text
docker build -f monte_carlo_service/Dockerfile monte_carlo_service
```

### Cloud Build trigger (GitHub / Cloud Source Repositories)

1. Open **Google Cloud Console → Cloud Build → Triggers** (or set this while creating the Cloud Run service).
2. **Configuration**: choose **Cloud Build configuration file (yaml or json)** — not “Dockerfile” only.
3. **Cloud Build configuration file location**: `cloudbuild.yaml` (root of the repo).
4. Match **Artifact Registry** to your project:
   - Edit defaults in `cloudbuild.yaml` (`_REGION`, `_AR_REPOSITORY`, `_IMAGE_NAME`, `_TAG`), **or**
   - Override **substitutions** on the trigger for the same variables.

After a successful build, point Cloud Run at the image:

`{_REGION}-docker.pkg.dev/{PROJECT_ID}/{_AR_REPOSITORY}/{_IMAGE_NAME}:{_TAG}`

### Cloud Run “Connect repository” wizard

If the wizard only offers a **Dockerfile** at the root:

- Switch the build step to use a **Cloud Build configuration file** and set it to **`cloudbuild.yaml`**, or  
- If the UI has **Dockerfile path** and **Build context**, set:
  - **Dockerfile path:** `monte_carlo_service/Dockerfile`
  - **Build context / Source:** `monte_carlo_service` (directory that contains the Dockerfile and `app/`)

## Runtime

The container listens on **port 8080** (see `monte_carlo_service/Dockerfile` / `CMD`).

## GitHub Actions

Workflow **`.github/workflows/deploy-monte-carlo-cloud-run.yml`** runs `gcloud builds submit` with **`--config cloudbuild.yaml`** from the repo root so CI matches Cloud Build triggers.
