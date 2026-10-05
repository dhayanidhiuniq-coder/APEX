import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="APEX Backend", version="0.1.0")

# Configure CORS - allow local frontend development
# Do not hard-code production domains; use env config where appropriate
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
# Allow comma-separated list
origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
