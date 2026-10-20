"""Identified, bounded HTTPS reads with normal TLS verification."""
from pathlib import Path
import ssl
import urllib.request


def fetch(url, timeout=60, limit=160_000_000):
    # The python.org macOS Python may not have its certificate bundle installed.
    # Use the OS CA bundle when present; never bypass certificate verification.
    context = ssl.create_default_context()
    if not context.get_ca_certs() and Path('/etc/ssl/cert.pem').exists():
        context = ssl.create_default_context(cafile='/etc/ssl/cert.pem')
    request = urllib.request.Request(url, headers={'User-Agent':'PedalLoop-local-MVP/0.2'})
    with urllib.request.urlopen(request,timeout=timeout,context=context) as response:
        body=response.read(limit+1)
    if len(body)>limit: raise ValueError('Provider response exceeds the local download limit. Try a smaller region.')
    return body
