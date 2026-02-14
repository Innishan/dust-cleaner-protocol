import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Dust Cleaner Protocol API")

cors_origins = os.getenv("CORS_ORIGINS", "")
allowed = [o.strip() for o in cors_origins.split(",") if o.strip()]

# fallback defaults (works if env var not set)
if not allowed:
    allowed = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://dust-cleaner-protocol.vercel.app",
        "https://dust-cleaner-protocol.vercel.app/",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
class AnalyzeReq(BaseModel):
    wallet: str

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/analyze")
def analyze(req: AnalyzeReq):
    """
    Calls your existing dust scan logic and returns JSON.
    """

    # IMPORTANT: import inside function so server boot doesn't crash if something imports web3 early
    from dust_scanner import run_stage2_public_dust_scan  # we'll create this wrapper in next step

    report = run_stage2_public_dust_scan(req.wallet)
    return report

