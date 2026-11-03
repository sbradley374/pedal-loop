#!/usr/bin/env python3
"""Single-instance beta entrypoint. Terminate HTTPS at a configured reverse proxy."""
import os
import logging
from pathlib import Path
from app import create_app, ROOT
from planner.storage import seed_data
from planner.staging import protect


def main():
    from waitress import serve
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s")
    directory=Path(os.environ.get('DATA_DIR',ROOT/'data'))
    seed_data(ROOT/'data',directory)
    application=create_app(data_dir=directory,
                           data=os.environ.get('ROAD_DATA') or directory/'providence.osm.json.gz',
                           imports=os.environ.get('ALLOW_IMPORTS','0')=='1',
                           public_origin=os.environ.get('PUBLIC_ORIGIN') or os.environ.get('RENDER_EXTERNAL_URL'))
    handler=application
    if os.environ.get('STAGING_USER') or os.environ.get('STAGING_PASSWORD'):
        handler=protect(application,os.environ.get('STAGING_USER'),os.environ.get('STAGING_PASSWORD'))
    settings={'host':os.environ.get('HOST','127.0.0.1'),
              'port':int(os.environ.get('PORT','8000')),
              'threads':8,'max_request_body_size':8192,'channel_timeout':30}
    proxy=os.environ.get('TRUSTED_PROXY')
    if proxy:
        if proxy=='*':raise ValueError('Specify the actual reverse proxy IP, not a wildcard.')
        settings.update(trusted_proxy=proxy,trusted_proxy_headers={'x-forwarded-for','x-forwarded-proto'})
    try:serve(handler,**settings)
    finally:application.service.close()


if __name__=='__main__':main()
