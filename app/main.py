import os
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from app.deps import init_db

# Routers
from app.routers import generate, content, storage, storage_pipeline, scheduler_api
from app.routers import auth_linkedin, linkedin_publish
from app.routers import thoughtpost


app = FastAPI(title="LinkedIn SaaS API", version="0.5.0")

# ---- Feature flag (default false) ----
ENABLE_OAUTH_LOGIN = os.getenv("ENABLE_OAUTH_LOGIN", "false").lower() == "true"

# ---- CORS (must be BEFORE routes mount) ----
# IMPORTANT: use a single CORSMiddleware. Credentials allowed only when not wildcard.
raw_origins = os.getenv("ALLOWED_ORIGINS", "*").strip()
ALLOWED_ORIGINS = ["*"] if raw_origins == "*" else [o.strip() for o in raw_origins.split(",") if o.strip()]
USE_CREDENTIALS = (ALLOWED_ORIGINS != ["*"])  # only true when you set a specific origin like https://tylerguilbault.github.io

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=USE_CREDENTIALS,  # must be True for cookies; False if wildcard
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---- Sessions (only when flag is ON) ----
if ENABLE_OAUTH_LOGIN:
    SESSION_SECRET = os.environ["SESSION_SECRET"]  # set in Render
    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET,
        same_site="none",     # cross-site (GH Pages -> Render)
        https_only=True       # required for same_site="none"
    )

print("CORS config ->", {"ALLOWED_ORIGINS": ALLOWED_ORIGINS, "allow_credentials": USE_CREDENTIALS})
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
