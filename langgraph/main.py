# main.py
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

load_dotenv()

app = FastAPI(
    title="ATS-HR Automation System",
    description="LangGraph-powered ATS and HR Decision automation using FastAPI",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "message": "ATS-HR Automation API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "ats_submit": "/ats/submit",
            "hr_decision": "/hr/decision"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)