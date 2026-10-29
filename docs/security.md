# Security and privacy

## Demo isolation

Use only the documented `--env-file .env.demo -f compose.demo.yaml` startup command. It selects the `driving-simulator-demo` project and a new synthetic MongoDB volume. The configuration does not mount local data directories, expose MongoDB, join a private stack's network, or reference a private database volume.

FastAPI is explicitly `APP_MODE=demo` and selects `driving_features_demo`. The connection helper does not read `.env` in Demo mode, ignores private URI/host overrides, and refuses another database name. Missing Demo credentials fail startup rather than falling back. Both normal CRUD/export endpoints and the dashboard use this isolated database. The fixed `/demo/features` reference endpoint also contains only fictional data.

Legacy live-compatible implementation identifiers remain internally where renaming would risk unnecessary changes. Local live Compose configuration, research adapters, participant labels, workbooks and exports are excluded from the public file set. Private Live operation is not activated by any documented public command. Existing private data and credentials are not migrated or rewritten.

## Credentials

`setup_demo.py` generates fresh Demo-only credentials in ignored `.env.demo`. It never opens or overwrites `.env`. `.env.example` contains placeholders only. Never commit real environment files, request headers, rendered Kong configuration, Compose environment dumps, logs or database backups. API keys stay on the Streamlit server; no credentials enter browser widgets or downloaded CSVs.

Development credentials previously shared outside their local configuration should be rotated before external use. Do not attempt to rotate a persistent MongoDB user by merely changing an environment file. Private credential rotation is deliberately outside this release preparation, which preserves private configuration unchanged.

## Release review

The previous local Git object store contained private research artifacts and was explicitly authorized for deletion. A new repository was initialized without carrying over the old metadata. Do not restore or publish old Git objects or backups. The first commit must contain only the reviewed release manifest; ignore rules alone do not establish safety.

`python scripts/audit_release.py` checks proposed tracked/untracked public candidates for forbidden artifacts, personal paths and credential-like literals. It does not read private datasets. This bounded static scan is not a guarantee against every possible secret; review changes before staging. Screenshots are regenerated from the new fictional Demo and inspected for branding and data disclosure.

## Deployment limitations

This is a localhost demonstration, not a publicly hardened clinical platform. A shared API key permits Demo CRUD; the UI is read-only but implicitly grants read access to anyone reaching its server. Keys are not user-level authorization. HTTP, in-memory rate limits and memory-based CSV exports are suitable for this scope. Any external deployment needs explicit review, TLS, proper user authorization, secret management, operational monitoring and a license decision. No deployment or publication is performed by the setup scripts.
