# GitHub Reusable Workflows Reference

This repository provides standardized, reusable GitHub Action workflows. By using these, every service in the TOB ecosystem inherits high-quality CI/CD logic with minimal configuration.

---

## 🐍 Python CI (`reusable-ci-python.yml`)
Standardized pipeline for Python services using **uv**.

### Inputs
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `python-version` | string | `3.12` | Version of Python to install. |
| `working-directory` | string | `.` | Root of the Python project. |
| `run-lint` | boolean | `true` | Whether to run Ruff check/format. |
| `run-test` | boolean | `true` | Whether to run Pytest. |
| `environment` | string | `production` | Sets the `ENV` variable for tests. |

### Example Usage
```yaml
jobs:
  ci:
    uses: Nicola-Ibrahim/Tracing-Objectives-Backwards-Devops/.github/workflows/reusable-ci-python.yml@main
    with:
      working-directory: ./backend
      python-version: '3.12'
```

---

## 📦 Node.js CI (`reusable-ci-node.yml`)
Standardized pipeline for JavaScript/TypeScript services using **pnpm**.

### Inputs
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `node-version` | string | `20` | Version of Node.js. |
| `package-manager` | string | `pnpm` | Choice of `pnpm`, `npm`, or `yarn`. |
| `working-directory` | string | `.` | Root of the Node project. |
| `run-lint` | boolean | `true` | Runs `pnpm lint`. |
| `run-test` | boolean | `true` | Runs `pnpm test`. |

### Example Usage
```yaml
jobs:
  ci:
    uses: Nicola-Ibrahim/Tracing-Objectives-Backwards-Devops/.github/workflows/reusable-ci-node.yml@main
    with:
      package-manager: 'pnpm'
      run-test: true
```

---

## 🐳 Docker CD (`reusable-cd-docker.yml`)
Automated image builds and distribution to **GitHub Container Registry (GHCR)**.

### Inputs
| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `image-name` | string | **Required** | The name of the image (e.g., `tob-backend`). |
| `dockerfile` | string | `./Dockerfile` | Path to the Dockerfile. |
| `context` | string | `.` | Docker build context reach. |
| `build-args` | string | - | Multi-line string of build arguments. |

### Tagging Strategy
This workflow automatically generates tags based on:
- `sha-<hash>`: For every commit.
- `latest`: Only for commits to the default branch (`main`).
- `vX.Y.Z`: When a semver tag is pushed.

### Example Usage
```yaml
jobs:
  deploy:
    uses: Nicola-Ibrahim/Tracing-Objectives-Backwards-Devops/.github/workflows/reusable-cd-docker.yml@main
    with:
      image-name: my-app
      dockerfile: ./infra/Dockerfile
    secrets:
      registry-password: ${{ secrets.GITHUB_TOKEN }}
```

---

## 🛠 Best Practices
1. **Always use `@main`**: For active internal development, or use specific tags (e.g., `@v1.0.0`) for strict stability.
2. **Secrets**: Most workflows default to using the repository's `GITHUB_TOKEN` for package access. If you need external registries, provide an explicit `registry-password` secret.
