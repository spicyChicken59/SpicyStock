FROM python:3.12-slim
WORKDIR /app
COPY requirements-bridge.txt ./
RUN pip install --no-cache-dir -r requirements-bridge.txt \
    && useradd --uid 10001 --create-home bridge \
    && mkdir /data && chown bridge:bridge /data
COPY src/broker_bridge ./src/broker_bridge
COPY docs ./docs
COPY data/symbols.txt ./data/symbols.txt
USER 10001:10001
EXPOSE 8000
ENV BRIDGE_DATABASE=/data/broker.sqlite3
CMD ["uvicorn", "src.broker_bridge.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
