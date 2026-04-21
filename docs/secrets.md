# Secrets Management Strategy

We use **Doppler** as the central source of truth for all environment variables and secrets. This ensures that secrets are never committed to version control and are synchronized across developer machines and CI/CD pipelines.

---

## 🏛 Architecture

### Projects & Configs
Each service (e.g., `backend`, `frontend`) has a dedicated **Project** in Doppler. Inside each project, we maintain standard **Configs**:
- `dev`: Local development secrets.
- `stg`: Staging / Preview environment secrets.
- `prd`: Production secrets.

### Secret Namespacing
Standardize secret names using `SCREAMING_SNAKE_CASE`.
- Prefixes: Use prefixes for service-specific secrets (e.g., `STRIPE_API_KEY`, `POSTGRES_PWD`).
- Global Secrets: Shared infrastructure secrets should be managed in a `common` project and referenced via Doppler's secret cross-referencing feature.

---

## 💻 Local Development Workflow

The **`platform-dev`** toolbox automates the synchronization of Doppler secrets to your local workspace.

### 1. Authentication
Run `tob-bootstrap` or manually:
```bash
doppler login
```

### 2. Synchronization
When you run `tob-dev up`, the toolbox performs the following:
1. Validates your Doppler identity (`doppler me`).
2. Downloads the secrets for your active project config.
3. Injects them into a local `.env` file (which is ignored by git).
4. Passes them into `docker compose` via `doppler run`.

---

## 🚀 CI/CD Integration

Our GitHub Action workflows automatically integrate with Doppler using **Service Tokens**.

### How it works:
1. The service repository stores a `DOPPLER_TOKEN` as a GitHub Action Secret.
2. The workflow installs the Doppler CLI.
3. Commands requiring secrets are prefixed with `doppler run --`:
   ```yaml
   - name: Run Build
     run: doppler run -- pnpm build
   ```

---

## 🛑 Security Standards
1. **Never Hardcode**: Forbidden to include any API key, password, or sensitive URL in code.
2. **Rotate Regularly**: High-privilege keys (AWS, Stripe) should be rotated every 90 days.
3. **Least Privilege**: Only grant developer access to the `dev` configuration unless explicitly required for debugging.
4. **Visibility**: Do not log raw secret values to the console. The Doppler CLI automatically masks secrets in its output.
