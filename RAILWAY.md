# Railway deployment

1. Connect this GitHub repository to a Railway service and deploy the `fix/railway-deployment` branch after merging this pull request.
2. Set the service root directory to the folder containing `main.py`, `requirements.txt`, and `Procfile` (the repository root for this project).
3. Add `META_ACCESS_TOKEN`, `META_VERIFY_TOKEN`, and `IG_ACCOUNT_ID` in Railway Variables. To enable POST webhook signature validation, also add `META_APP_SECRET` from the same Meta app. `GRAPH_API_VERSION` may be set to `v26.0`.
4. Railway installs dependencies from `requirements.txt` and starts the app with the `Procfile`.
5. Configure the Meta webhook callback URL as `https://<your-railway-domain>/webhook` and use the same verification token as `META_VERIFY_TOKEN`.

Never commit `.env`, `config.py`, or actual API tokens. The SQLite database is stored in the service filesystem; use a Railway volume and set `DB_FILE` to a file path inside the mounted volume if chat history must persist across redeploys. The current default remains unchanged for backward compatibility.
