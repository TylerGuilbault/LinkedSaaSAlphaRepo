import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from app.deps import init_db

# Routers
from app.routers import generate, content, storage, storage_pipeline, scheduler_api
from app.routers import auth_linkedin, linkedin_publish
from app.routers import thoughtpost


app = FastAPI(title="LinkedIn SaaS API", version="0.5.0")

raw = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = ["*"] if raw.strip() == "*" else [o.strip() for o in raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,   # keep False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

print("MOUNTING ROUTERS… main.py at runtime is:", __file__)


@app.on_event("startup")
def _startup():
    init_db()

@app.get("/")
def root():
    return {"message": "LinkedIn SaaS API is running!"}

@app.get("/health")
def health():
    return {"ok": True}

# Mount routes
app.include_router(generate.router)           # /rss/*
app.include_router(content.router)            # /generate/*
app.include_router(storage.router)            # /storage/*
app.include_router(storage_pipeline.router)   # /pipeline/*
app.include_router(scheduler_api.router)      # /scheduler/*
app.include_router(auth_linkedin.router)      # /auth/linkedin/*
app.include_router(linkedin_publish.router)   # /linkedin/*
app.include_router(thoughtpost.router)
