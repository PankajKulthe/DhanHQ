# Setup Guide

1. Copy `.env.example` to `.env`.
2. Generate `CREDENTIAL_KEY` with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

3. Start services:

```bash
docker compose up --build
```

4. Visit `http://localhost:8000/docs` and run `/health`.
5. Open `http://localhost:5173` and connect Angel One in paper mode first.

## Production Checklist

- Replace all secrets.
- Set Postgres credentials to managed secret values.
- Put backend behind TLS.
- Configure broker postback URL on HTTPS port 443.
- Keep `LIVE_TRADING_ENABLED=false` until paper trading reconciliation is clean.
- Add database backups and log retention.
