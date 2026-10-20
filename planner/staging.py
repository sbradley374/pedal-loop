"""Optional shared-password gate for a private HTTPS beta, not user accounts."""
import base64
import hmac


def protect(application, username, password):
    if not username or not password:
        raise ValueError('Set both STAGING_USER and STAGING_PASSWORD for private staging.')
    if ':' in username:
        raise ValueError('STAGING_USER cannot contain a colon.')
    expected = b'Basic '+base64.b64encode(f'{username}:{password}'.encode('utf-8'))
    def gated(environ, start_response):
        # Infrastructure health checks reveal no routes, settings, or data.
        if environ.get('REQUEST_METHOD') == 'GET' and environ.get('PATH_INFO') == '/api/health':
            return application(environ, start_response)
        supplied = environ.get('HTTP_AUTHORIZATION','').encode('utf-8')
        if hmac.compare_digest(supplied, expected):
            return application(environ, start_response)
        body = b'Private beta. Sign in with the staging credentials.'
        start_response('401 Unauthorized', [
            ('WWW-Authenticate','Basic realm="Pedal Loop beta", charset="UTF-8"'),
            ('Content-Type','text/plain; charset=utf-8'),('Content-Length',str(len(body))),
            ('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')])
        return [body]
    return gated
