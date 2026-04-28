#!/bin/bash
set -e

echo "=== CadenceWorks Production Startup ==="

# Start webhook server on internal port 5005
echo "Starting webhook server (port 5005)..."
WEBHOOK_PORT=5005 python engine/webhook_server.py &

# Start Streamlit on internal port 8501 (localhost only — nginx proxies to it)
echo "Starting Streamlit dashboard (port 8501)..."
streamlit run app.py \
    --server.port 8501 \
    --server.headless true \
    --server.address 127.0.0.1 &

# Give both servers time to initialise before nginx starts
echo "Waiting for services to initialise..."
sleep 6

# Generate nginx config with the actual Railway $PORT value
envsubst '${PORT}' < nginx.conf.template > /tmp/nginx.conf

echo "Starting nginx on port ${PORT}..."
nginx -c /tmp/nginx.conf -g "daemon off;"
