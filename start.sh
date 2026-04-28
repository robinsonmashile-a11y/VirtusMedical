#!/bin/bash
# CadenceWorks service launcher
# Set SERVICE=webhook on the Railway webhook service
# Leave unset (or SERVICE=dashboard) on the Streamlit service

if [ "$SERVICE" = "webhook" ]; then
    echo "Starting webhook server..."
    python engine/webhook_server.py
else
    echo "Starting Streamlit dashboard..."
    streamlit run app.py --server.port $PORT --server.headless true
fi
