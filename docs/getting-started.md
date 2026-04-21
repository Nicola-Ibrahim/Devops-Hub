# Getting Started with Platform-Dev

This guide will walk you through setting up your local development environment using the TOB standardized `platform-dev` toolbox.

## 📋 Prerequisites

Before you begin, ensure you have the following installed:
1.  **Python 3.12+**
2.  **Docker Desktop** (running)
3.  **Homebrew** (for macOS users)

## 🚀 Step-by-Step Setup

### 1. Install `uv`
We use `uv` for lightning-fast Python package management.
```bash
brew install uv
```

### 2. Configure Secrets (Doppler)
We use Doppler to securely manage environment variables. Even if the tool is not installed, our bootstrap process will help you.
```bash
# Login to your Doppler account
doppler login
```

### 3. Initialize the Repository
Go to your project directory (e.g., `backend`) and run:
```bash
# Install all dependencies and setup the environment
uv sync
```

### 4. Bootstrap the Environment
Once dependencies are synced, run the standardized bootstrap command:
```bash
poe bootstrap
```
This will:
- Audit your system for required binaries.
- Install missing tools (`doppler`, etc.).
- Sync the latest `.env` files.
- Boot the Docker infrastructure.

### 5. Start Development
Now you can start your local development server:
```bash
poe dev up
```

## 🛠 Common Commands

- `poe dev up`: Start everything (Secrets + DB + Server).
- `poe dev down`: Stop everything and clean caches.
- `poe test`: Run the test suite.

---

> [!TIP]
> If you encounter issues with Docker containers not starting, ensure Docker Desktop is running and try `poe dev down` before running `up` again.
