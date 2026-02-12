import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Dust Cleaner Protocol API")

# Allow local dev UI to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
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

