# Dashboard

Start the isolated Demo using the README command and open **http://localhost:18501**. The server reads the synthetic MongoDB through Kong and normal FastAPI endpoints. No browser input can select a private database. Every page displays a fictional-data banner.

| Page | Purpose |
| --- | --- |
| Overview | Record count, scenario distribution and label distribution |
| Feature Explorer | Subject/scenario/label filters, pagination and numerical feature details |
| Data Quality | Missing/invalid cells, feature completeness and modality availability |
| Dataset Export | Select filters and feature groups, preview, download CSV |

## Walkthrough

1. Overview starts with 60 fictional observations across five scenarios and three labels.
2. In Feature Explorer select scenario 1 and Health; inspect an observation and change page size.
3. In Data Quality select scenario 5. Simulator eligibility is zero because this scenario is physiological-only.
4. In Dataset Export select ECG and EEG groups, then download the fictional CSV.

Missing rate is empty feature cells divided by selected records ? feature fields. Structurally absent scenario fields are included, so this is not a clinical quality score. Modality availability means at least one finite numerical value per eligible record; simulator eligibility excludes scenario 5. Invalid non-null values are counted separately. Unavailable denominators display no rate.

The UI uses server-generated subject aliases. Exports exclude source IDs and preserve original feature names and missing values. Optional subject grouping keys change on server restart. Alias substitution does not make real clinical data publishable; this release uses fictional records only. Responses are cached server-side for up to 60 seconds; Refresh data clears the cache.

## Synthetic screenshots

- [Overview](screenshots/overview.png)
- [Feature Explorer](screenshots/feature-explorer.png)
- [Data Quality](screenshots/data-quality.png)
- [Dataset Export](screenshots/dataset-export.png)
- [Mobile overview](screenshots/overview-mobile.png)

Capture only the fictional Demo with its banner visible. Never capture environment files, credentials, private dashboards, Compass records or request headers. For optional automated screenshots:

```powershell
python -m pip install playwright==1.60.0 greenlet==3.1.1
# Uses installed Edge/Chrome when available; otherwise install Chromium:
python -m playwright install chromium
python scripts/verify_dashboard_browser.py
```

The helper visits all four pages, checks a CSV download, checks browser messages for source IDs/API keys, and captures desktop and mobile views. Its private verification output is ignored under `.release-audit/`. It does not write to MongoDB.
