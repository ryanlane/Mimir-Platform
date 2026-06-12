# For even more verbose debugging
.venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 5000 \
    --workers 1 \
    --reload \
    --log-level trace \
    --access-log \
    --use-colors