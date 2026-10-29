# v1.0.0 release verification

## Recommendation

**Technical GO for the reviewed public file set**, pending the owner's explicit first-commit and publication approval. No commit, tag, remote, push or external deployment was created. License decision remains pending; this is not presented as a licensed open-source release.

## Changes

- Added `compose.demo.yaml`, a separate Demo environment helper and schema-validated synthetic initialization.
- Retained the four-service architecture and existing API behavior; normal Demo CRUD/statistics/exports now use only `driving_features_demo.scenario_features`.
- Added fail-closed database selection and ignored private URI overrides in Demo. Demo-created subject codes must be fictional P99 codes.
- Kept local private Compose configuration out of Git, with explicit Live opt-in. Private `.env`, data, database volume and original signal algorithms were not overwritten or migrated.
- Updated public titles, Kong names, dashboard labels, English documentation and fictional screenshots. A few internal Live-compatibility identifiers remain, as permitted; public UI/docs/configuration names use the new identity.
- Added allowlist-based ignore rules, candidate-file scanning and essential Demo verification tests. Excluded private adapters, raw-data tools, participant tables, workbooks, exports, caches and obsolete executables from the proposed commit.

## Executed checks

| Check | Actual result |
| --- | --- |
| Full selected public suite, integration flags enabled | **46 passed**, no failures or skips |
| Final explicit-project Demo isolation/CRUD recheck | **4 passed** |
| Public-file-only checkout, no private adapters/data/environment files | **41 passed, 5 integration tests skipped** |
| Docker build/start and health checks | MongoDB, FastAPI, Kong, Streamlit healthy |
| Real Demo MongoDB/API | 60 fictional records; create, duplicate 409, PATCH, lookup, filtered CSV and test-record cleanup passed |
| Kong | Routing passed; missing/invalid keys 401; valid key 200; rate limit 429 |
| Browser | All four pages passed; fictional 60-row CSV downloaded; desktop 1440 px and mobile 390 px checked |
| Browser disclosure | No source subject codes or server API key in captured Streamlit websocket messages |
| Credentials | Four current private/Demo secret values checked against proposed public files; zero exact matches |
| Static release scan | No forbidden datasets, personal paths, credential-like literals or non-English text findings |
| Private preservation | Private environment byte hash unchanged; research output file counts/total sizes unchanged; no private database queries executed |
| Git | Authorized old object store deleted without backup; fresh `main` repository initialized; zero staged files, refs, commits or remotes |

An upstream Streamlit/Altair deprecation warning remains; tests still pass. The private-file preservation check used metadata and the environment hash, not a new read of private clinical records. No tests queried or regenerated the private research database or outputs. Private raw-extraction tests were intentionally not selected for the public distribution; equivalent public API/storage behavior is covered using fictional data.

## Isolation evidence

The executed Compose configuration has its own `driving-simulator-demo` project and `driving-simulator-demo_synthetic_mongodb_data` volume. MongoDB has no host port, FastAPI has no host port, the database network is internal, and there are no bind mounts of local data. Only localhost gateway/dashboard ports are published. Streamlit uses Kong and the normal API with `DASHBOARD_BACKEND=store`; no MongoDB credentials are sent to Streamlit.

The Demo environment helper never opens `.env`. Demo runtime ignores generic private MongoDB URI/host overrides and rejects a different database name. The initializer imports only the fictional generator; private processing adapters are excluded from images. Synthetic test writes were removed only from the dedicated Demo database. The seed is idempotent and does not overwrite existing Demo edits.

## Publication file review

See [release-files.txt](release-files.txt) for the exact proposed first-commit paths. Run `python scripts/audit_release.py` to recompute count, total bytes and findings before staging. `git add --dry-run --all` was inspected; no actual staging was performed. The final manifest and this report are documentation-only additions after the clean-checkout code test.

Proposed initial commit message: `feat: add synthetic driving simulator data management demo`.

## Remaining limitations

- Previously shared private development credentials require rotation before external use. They were not rotated here because private configuration must remain unchanged. The public Demo uses separately generated credentials.
- Localhost HTTP, a shared write-capable API key and single-instance in-memory rate limiting are not a production access-control design.
- CSV profiling/export is in memory; the fixture is illustrative and has no clinical validity.
- Live compatibility is retained locally, but private Live adapters/configuration and raw-sensor algorithms are not part of this public release.
- Static/exact-match scanning and browser inspection are bounded checks, not a universal guarantee against future disclosure. Re-audit new changes.
- The license is pending by instruction. Stop before committing or publishing.
