from __future__ import annotations
import typer
from app.core.config import settings

app_cli = typer.Typer(help="CLI for app-services")

def _common_env():
    host = settings.HOST
    port = settings.PORT
    app_module = settings.APP_MODULE
    return app_module, host, port

@app_cli.command()
def dev(
    host: str | None = None,
    port: int | None = None,
):
    """
    Starts in development mode (auto-reload).
    """
    import uvicorn
    app_module, h, p = _common_env()
    if host: h = host
    if port: p = port
    uvicorn.run(app_module, host=h, port=p, reload=True)

@app_cli.command()
def serve(
    host: str | None = None,
    port: int | None = None,
    workers: int = typer.Option(2, help="Workers for production"),
):
    """
    Starts in production mode (no reload).
    """
    import uvicorn
    app_module, h, p = _common_env()
    if host: h = host
    if port: p = port
    uvicorn.run(app_module, host=h, port=p, workers=workers)

@app_cli.command()
def check():
    """
    Shows basic effective configuration.
    """
    app_module, host, port = _common_env()
    typer.echo(f"APP_MODULE={app_module}")
    typer.echo(f"HOST={host}")
    typer.echo(f"PORT={port}")

if __name__ == "__main__":
    app_cli()