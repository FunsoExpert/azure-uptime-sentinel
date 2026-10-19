import os
import logging
import time
import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

import azure.functions as func
import requests

app = func.FunctionApp()


@app.timer_trigger(schedule="0 * * * * *", arg_name="timer", run_on_startup=False, use_monitor=False)
def uptime_probe(timer: func.TimerRequest) -> None:
    logging.info("Uptime Sentinel probe execution started.")

    raw_urls = os.environ.get("TARGET_URLS", "https://microsoft.com")
    urls = [u.strip() for u in raw_urls.split(",") if u.strip()]

    for url in urls:
        check_endpoint(url)


def check_endpoint(url: str) -> None:
    start_time = time.time()
    status_result = "DOWN"
    status_code = 0
    ssl_days_remaining = None

    try:
        # 1. HTTP status & latency
        response = requests.get(url, timeout=10)
        latency_ms = int((time.time() - start_time) * 1000)
        status_code = response.status_code
        status_result = "UP" if 200 <= status_code < 400 else "DEGRADED"

        # 2. SSL expiry (HTTPS only)
        if url.lower().startswith("https://"):
            ssl_days_remaining = get_ssl_expiry_days(url)
            if ssl_days_remaining is not None and ssl_days_remaining < 15:
                logging.warning(f"SSL_WARNING | URL: {url} | Certificate expires in {ssl_days_remaining} days")

        log = logging.info if status_result == "UP" else logging.warning
        log(
            f"CHECK_RESULT | URL: {url} | Status: {status_result} | Code: {status_code} "
            f"| Latency: {latency_ms}ms | SSL Days: {ssl_days_remaining}"
        )

    except requests.exceptions.RequestException as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logging.error(f"CHECK_FAILURE | URL: {url} | Status: DOWN | Error: {e} | Latency: {latency_ms}ms")


def get_ssl_expiry_days(url: str):
    """Days until the server certificate expires, using only the standard library."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    port = parsed.port or 443
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()  # validated cert as a dict
                expires = ssl.cert_time_to_seconds(cert["notAfter"])
                expiry_dt = datetime.fromtimestamp(expires, tz=timezone.utc)
                return (expiry_dt - datetime.now(timezone.utc)).days
    except Exception as e:
        logging.error(f"SSL_CHECK_FAILURE | Host: {hostname} | Error: {e}")
        return None
