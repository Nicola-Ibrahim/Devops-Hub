"""FastAPI CLI entrypoint; import only when starting a configured HTTP host."""

from containers.http import create_app

app = create_app()
