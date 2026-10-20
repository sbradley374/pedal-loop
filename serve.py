#!/usr/bin/env python3
"""Single-instance beta entrypoint. Terminate HTTPS at a configured reverse proxy."""
import os
from pathlib import Path
from app import create_app, ROOT


def main():
    from waitress import serve
    directory=Path(os.environ.get('DATA_DIR',ROOT/'data'))
    application=create_app(data_dir=directory,
                           data=os.environ.get('ROAD_DATA') or directory/'providence.osm.json.gz',
                           imports=os.environ.get('ALLOW_IMPORTS','0')=='1',
                           public_origin=os.environ.get('PUBLIC_ORIGIN'))
    settings={'host':os.environ.get('HOST','127.0.0.1'),
              'port':int(os.environ.get('PORT','8000')),
              'threads':8,'max_request_body_size':8192,'channel_timeout':30}
    proxy=os.environ.get('TRUSTED_PROXY')
    if proxy:
        if proxy=='*':raise ValueError('Specify the actual reverse proxy IP, not a wildcard.')
        settings.update(trusted_proxy=proxy,trusted_proxy_headers={'x-forwarded-for','x-forwarded-proto'})
    try:serve(application,**settings)
    finally:application.service.close()


if __name__=='__main__':main()
