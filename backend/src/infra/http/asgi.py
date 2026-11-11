"""FastAPI CLI entrypoint; import only when starting a configured HTTP host."""

from infra.http.app import create_app

app = create_app()
