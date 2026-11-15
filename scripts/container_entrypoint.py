"""Container start-up: prepare persistent state, render secrets from the environment, start the app.

State lives on one volume (SPAMGUARD_STATE_DIR, default /var/lib/spamguard):
  users/ logs/ backups/   -> linked from data/ in the image
  models/                 -> linked from models/; baseline artifacts are refreshed from the
                             image on every start, released versions and active.json persist.

Secrets are read from environment variables and written to ~/.streamlit/secrets.toml
(mode 0600) unless a secrets file is already mounted.
"""
import json
import os
from pathlib import Path
import shutil
import sys

BASELINE_FILES = ("spam_classifier_nb.pkl", "spam_classifier_svm.pkl", "tfidf_vectorizer.pkl", "metrics.json")


def toml_string(value: str) -> str:
    """JSON string escaping is valid TOML basic-string escaping."""
    return json.dumps(str(value), ensure_ascii=False)


def render_secrets(env) -> str:
    """Returns secrets.toml content for the given environment, or '' when sign-in is not configured.

    Raises ValueError when sign-in is partly configured, so a misconfigured deployment
    fails at start-up instead of running with a weak or missing cookie secret.
    """
    client_id = env.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = env.get("GOOGLE_CLIENT_SECRET", "").strip()
    admin_emails = [e.strip() for e in env.get("SPAMGUARD_ADMIN_EMAILS", "").split(",") if e.strip()]
    lines = []
    if client_id or client_secret:
        public_url = env.get("SPAMGUARD_PUBLIC_URL", "").strip().rstrip("/")
        cookie_secret = env.get("SPAMGUARD_COOKIE_SECRET", "").strip()
        if not (client_id and client_secret):
            raise ValueError("Set both GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET, or neither.")
        if not public_url.startswith("https://") and not public_url.startswith("http://localhost"):
            raise ValueError("SPAMGUARD_PUBLIC_URL must be the public https:// address of the app.")
        if len(cookie_secret) < 32 or cookie_secret.upper().startswith(("REPLACE", "CHANGE")):
            raise ValueError("SPAMGUARD_COOKIE_SECRET must be a random value of at least 32 characters.")
        scope = "openid email profile https://www.googleapis.com/auth/gmail.readonly"
        metadata = "https://accounts.google.com/.well-known/openid-configuration"
        lines += [
            "[auth]",
            f"redirect_uri = {toml_string(public_url + '/oauth2callback')}",
            f"cookie_secret = {toml_string(cookie_secret)}",
            'expose_tokens = ["access"]',
            "",
            "[auth.google]",
            f"client_id = {toml_string(client_id)}",
            f"client_secret = {toml_string(client_secret)}",
            f"server_metadata_url = {toml_string(metadata)}",
            f'client_kwargs = {{ scope = {toml_string(scope)}, prompt = "consent select_account" }}',
            "",
        ]
        if env.get("SPAMGUARD_ENABLE_GMAIL_ACTIONS", "") == "1":
            modify_scope = "openid email profile https://www.googleapis.com/auth/gmail.modify"
            lines += [
                "[auth.googleactions]",
                f"client_id = {toml_string(client_id)}",
                f"client_secret = {toml_string(client_secret)}",
                f"server_metadata_url = {toml_string(metadata)}",
                f'client_kwargs = {{ scope = {toml_string(modify_scope)}, prompt = "consent select_account" }}',
                "",
            ]
    if lines or admin_emails:
        lines += ["[app]", "admin_emails = [" + ", ".join(toml_string(e) for e in admin_emails) + "]", ""]
    return "\n".join(lines)


def prepare_state(app_root: Path, state_dir: Path, baseline_dir: Path) -> None:
    for name in ("users", "logs", "backups", "models"):
        (state_dir / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    if baseline_dir.is_dir():
        for name in BASELINE_FILES:
            source = baseline_dir / name
            if source.exists():
                shutil.copy2(source, state_dir / "models" / name)


def main() -> None:
    app_root = Path(__file__).resolve().parents[1]
    state_dir = Path(os.environ.get("SPAMGUARD_STATE_DIR", "/var/lib/spamguard"))
    prepare_state(app_root, state_dir, Path(os.environ.get("SPAMGUARD_BASELINE_MODELS", "/opt/spamguard/baseline-models")))

    project_secrets = app_root / ".streamlit" / "secrets.toml"
    home_secrets = Path.home() / ".streamlit" / "secrets.toml"
    if not project_secrets.exists():
        try:
            content = render_secrets(os.environ)
        except ValueError as error:
            sys.exit(f"Configuration error: {error}")
        if content:
            home_secrets.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(home_secrets, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
        elif home_secrets.exists():
            home_secrets.unlink()

    if os.environ.get("SPAMGUARD_ENV") == "production" and os.environ.get("SPAMGUARD_LOCAL_ADMIN") == "1":
        sys.exit("Configuration error: SPAMGUARD_LOCAL_ADMIN must not be set in production.")

    os.chdir(app_root)
    os.execvp(sys.executable, [sys.executable, "-m", "streamlit", "run", "app.py",
                               "--server.port", os.environ.get("PORT", "8501"), "--server.address", "0.0.0.0"])


if __name__ == "__main__":
    main()
