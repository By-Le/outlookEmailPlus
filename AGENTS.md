# Repository Guidelines

## Project Structure & Module Organization

- `outlook_web/`: Flask backend (`app.py`, `routes/`, `services/`, `repositories/`, `security/`).
- `static/` + `templates/`: frontend assets and HTML templates.
- `data/`: runtime data (SQLite DB default: `data/outlook_accounts.db`). Do not commit production data.
- `tests/`: unit/contract tests (CI runs `unittest` discovery).
- Top-level entrypoints: `web_outlook_app.py` (web app), plus utility scripts like `start.py` / `outlook_mail_reader.py`.

## Build, Test, and Development Commands

Local (Windows/macOS/Linux):

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python web_outlook_app.py
```

Testing:

```bash
python -m unittest discover -s tests -v
```

Docker:

```bash
docker build -t outlook-email-plus .
docker run --rm -p 5000:5000 -v ./data:/app/data outlook-email-plus
```

## Coding Style & Naming Conventions

- Python: format with `black` (line length `127`) and sort imports with `isort` (profile `black`).
- Lint/type/security checks used in CI: `flake8` (incl. complexity), `mypy`, `bandit`.
- Naming: modules and functions use `snake_case`; classes use `PascalCase`; constants use `UPPER_SNAKE_CASE`.

## Testing Guidelines

- Prefer focused unit tests in `tests/test_*.py`; keep tests deterministic (avoid network calls unless explicitly mocked).
- Add/adjust tests when changing `outlook_web/` service logic or security-sensitive behavior (auth, token refresh, encryption).

## Commit & Pull Request Guidelines

- Commit messages follow a Conventional-Commits-like prefix: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `ci:`, `style:`, `release:`.
- PRs should follow `.github/PULL_REQUEST_TEMPLATE.md`: include what changed, why, and screenshots for UI changes; link related issues when applicable.

## Security & Configuration Tips

- Configure via environment variables or `.env` (see `.env.example`). Always set a strong `SECRET_KEY`; never commit credentials or refresh tokens.
- If debugging locally, use sample data and keep secrets out of logs and screenshots.
