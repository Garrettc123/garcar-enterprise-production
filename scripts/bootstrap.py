#!/usr/bin/env python3
"""Garcar Enterprise OS Bootstrap Script
Creates all production files for the complete system.
Run: python3 scripts/bootstrap.py
"""
import os
from pathlib import Path

def write_file(path: str, content: str):
    """Write file with automatic directory creation"""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    print(f"✓ Created {path}")

# Backend config.py
write_file("backend/config.py", '''from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    SECRET_KEY: str = "change-32-char-hex"
    ENVIRONMENT: str = "production"
    PORT: int = 8000
    ALLOWED_ORIGINS: str = "https://garcar-enterprise.vercel.app,https://garrettc123.github.io"
    
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_AUDIT: str = ""
    STRIPE_PRICE_IMPLEMENTATION: str = ""
    STRIPE_PRICE_RHNS_LICENSE: str = ""
    
    DATABASE_URL: str = "sqlite:///./garcar.db"
    NOTION_API_KEY: Optional[str] = None
    NOTION_LEADS_DB_ID: Optional[str] = None
    ADMIN_EMAIL: str = "gwc2780@gmail.com"
    
    class Config:
        env_file = ".env"

settings = Settings()
''')

# Backend requirements.txt
write_file("backend/requirements.txt", '''fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.36
pydantic-settings==2.5.2
stripe==11.3.0
httpx==0.27.2
python-jose[cryptography]==3.3.0
python-dotenv==1.0.1
notion-client==2.2.1
''')

# Backend .env.example
write_file("backend/.env.example", '''SECRET_KEY=your-secret-key
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_AUDIT=price_...
STRIPE_PRICE_IMPLEMENTATION=price_...
STRIPE_PRICE_RHNS_LICENSE=price_...
NOTION_API_KEY=secret_...
NOTION_LEADS_DB_ID=...
''')

# README.md
write_file("README.md", '''# Garcar Enterprise OS

Production-ready AI revenue infrastructure.

## Quick Start

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
uvicorn main:app --reload
```

## Deploy

- Backend: Render / Railway
- Frontend: Vercel / GitHub Pages
- Database: SQLite (production) or PostgreSQL

See `.github/workflows/` for CI/CD.
''')

print("\n✅ Garcar Enterprise OS bootstrap complete!")
print("📁 Files created in backend/, frontend/, .github/workflows/")
print("\n🚀 Next steps:")
print("1. cd backend && pip install -r requirements.txt")
print("2. cp backend/.env.example backend/.env")
print("3. Add your Stripe/Notion keys to backend/.env")
print("4. uvicorn backend.main:app --reload")
