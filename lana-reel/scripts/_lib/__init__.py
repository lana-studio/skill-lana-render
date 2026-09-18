"""Shared library for the reel-skill scripts (scripts/reel/ and scripts/lana/).

Stdlib only. Never imports urllib/http.client/socket/requests/httpx (that is
scripts/lana/transfer.py's job alone — it's the only script that touches the
network at all) and never reads an environment variable whose name contains
TOKEN/SECRET/CREDENTIAL/PASSWORD.
"""
