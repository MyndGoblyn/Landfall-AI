# LandFall AI

LandFall AI is a deterministic Commander deck-analysis and recommendation
application. The production frontend runs on Cloudflare Workers Static Assets;
FastAPI remains on Render and persists data in MongoDB Atlas.

## Local checks

```powershell
npm.cmd ci --prefix frontend
npm.cmd run smoke:source --prefix frontend
npm.cmd run build --prefix frontend
backend\.venv\Scripts\python.exe -m pytest -q
```

Install backend development dependencies with:

```powershell
python -m pip install -r backend\requirements-dev.txt
```

## Operations

- [Production setup](PRODUCTION_SETUP_GUIDE.md)
- [Cloudflare deployment](CLOUDFLARE_DEPLOYMENT_GUIDE.md)
- [Quality checklist](QA_CHECKLIST.md)
- [Candidate catalog](docs/CANDIDATE_CATALOG.md)
- [Pipeline optimization record](docs/PIPELINE_OPTIMIZATION.md)
