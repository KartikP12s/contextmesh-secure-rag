FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY backend ./backend
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-deps . && useradd -m app && mkdir data && chown app data
COPY scripts ./scripts
COPY fixtures ./fixtures
RUN mkdir docs && chown app docs
USER app
EXPOSE 8010
CMD ["uvicorn", "contextmesh.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8010"]
