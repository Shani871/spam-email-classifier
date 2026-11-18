# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SPAMGUARD_ENV=production \
    SPAMGUARD_STATE_DIR=/var/lib/spamguard \
    SPAMGUARD_BASELINE_MODELS=/opt/spamguard/baseline-models \
    SPAMGUARD_DATABASE_URL=sqlite:////var/lib/spamguard/spamguard.db \
    SPAMGUARD_BACKUP_DIR=/var/lib/spamguard/backups \
    STREAMLIT_CLIENT_SHOW_ERROR_DETAILS=none \
    STREAMLIT_CLIENT_TOOLBAR_MODE=viewer \
    MPLCONFIGDIR=/tmp/matplotlib

# OCR for the Screenshot/QR source (English + Hindi) and libraries OpenCV needs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-hin libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin spamguard
WORKDIR /app

COPY requirements-lock.txt ./
RUN pip install -r requirements-lock.txt \
    && pip install pytesseract opencv-python-headless

COPY app.py ./
COPY .streamlit/config.toml .streamlit/config.toml
COPY app_pages app_pages
COPY assets assets
COPY src src
COPY migrations migrations
COPY scripts scripts
COPY data/detection_evaluation_set.json data/detection_evaluation_set.json
COPY dataset/spam.csv dataset/emails.csv dataset/ham_diverse.csv dataset/
COPY models/spam_classifier_nb.pkl models/spam_classifier_svm.pkl models/tfidf_vectorizer.pkl models/metrics.json /opt/spamguard/baseline-models/

# All mutable state is on one volume; the app paths are links into it.
RUN mkdir -p /var/lib/spamguard/logs /var/lib/spamguard/backups /var/lib/spamguard/models \
    && ln -s /var/lib/spamguard/logs data/logs \
    && ln -s /var/lib/spamguard/backups data/backups \
    && ln -s /var/lib/spamguard/models models \
    && chown -R spamguard:spamguard /var/lib/spamguard

USER spamguard
VOLUME ["/var/lib/spamguard"]
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8501/_stcore/health || exit 1

CMD ["python", "scripts/container_entrypoint.py"]
