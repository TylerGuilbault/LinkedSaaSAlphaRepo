#!/bin/bash
set -e

# Ensure .env exists
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo ".env created from .env.example"
    else
        echo "LINKEDIN_CLIENT_ID=dummy" > .env
        echo "LINKEDIN_CLIENT_SECRET=dummy" >> .env
        echo "FERNET_KEY=dummykeydummykeydummykeydummykey" >> .env
        echo "LINKEDIN_REDIRECT_URI=http://localhost/callback" >> .env
        echo "LINKEDIN_SCOPES=openid profile w_member_social" >> .env
        echo ".env created with dummy values"
    fi
fi

# Run SQLite migrations
python3 app/db/migrate_member_id.py

# Start Uvicorn
uvicorn app.main:app --port 8000
