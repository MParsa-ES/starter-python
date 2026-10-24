"""Minimal health endpoint for the Software Engineering Lab."""

from fastapi import FastAPI

app = FastAPI(
    title="Starter Service",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    redirect_slashes=False,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok its really good"}
print("Test a Pull Request")
print("Test a Pull Request from Abolfazl Tajik")
