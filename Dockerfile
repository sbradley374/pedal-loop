FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-hosted.txt ./
RUN pip install --no-cache-dir -r requirements-hosted.txt && useradd --create-home --uid 10001 pedal
COPY --chown=pedal:pedal app.py serve.py ./
COPY --chown=pedal:pedal planner/ planner/
COPY --chown=pedal:pedal web/ web/
COPY --chown=pedal:pedal data/ data/
COPY --chown=pedal:pedal scripts/ scripts/
USER pedal
ENV HOST=0.0.0.0 PORT=8000 DATA_DIR=/app/data ALLOW_IMPORTS=0
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4)"
CMD ["python", "serve.py"]
