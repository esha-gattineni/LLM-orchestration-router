"""
Azure Functions Entry Point
---------------------------
Wraps the FastAPI app with azure-functions-python-worker so it can be
deployed as an HTTP-triggered Function behind Azure API Management.

Routing overhead target: <200ms (p95 in load tests at 500 req/min).
"""

import azure.functions as func
from azure.functions import AsgiMiddleware
from app.main import app

# ASGI middleware bridges Azure Functions HTTP trigger → FastAPI
main = func.AsgiFunctionApp(app=app, http_auth_level=func.AuthLevel.ANONYMOUS)
