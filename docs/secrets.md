# Runtime configuration and secrets

Local Compose reads ignored `backend/.env` and `frontend/.env` files. Run
`python3 scripts/helpers/init_env.py` to initialize missing local files without
printing values. Existing complete credentials are preserved; restore the backend
env file if an existing database volume is retained. Never regenerate credentials
to recover access to an initialized database.

The backend file holds local database and platform credentials. The frontend file
holds its server-side API URL and must never receive backend secrets. Keep both
private and out of images, source control, screenshots and logs. Resolved Compose
configuration and container inspection can expose environment values.

There is no active Doppler synchronization or server secret-delivery integration.
Operator-managed hosting and future deployment credentials require separately
approved configuration. CI uses isolated test inputs and short-lived cloud access
where image publishing is configured. See [operations](operations.md).
