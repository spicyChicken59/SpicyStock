"""Public reader with a separate, receipt-independent process liveness route."""
from src.morning_service import application

DATABASE = '/srv/spicystock/morning.sqlite'
ALLOWED_ORIGIN = 'https://spicychicken59.github.io'


def create_app(reader=None):
    read = reader if reader is not None else application(DATABASE, allowed_origin=ALLOWED_ORIGIN)

    def app(environ, start_response):
        if environ.get('PATH_INFO') != '/healthz':
            return read(environ, start_response)
        status = '200 OK'
        body = b'{"status":"alive","scope":"process_liveness_only"}\n'
        if environ.get('REQUEST_METHOD') != 'GET':
            status, body = '405 Method Not Allowed', b'{"status":"method_not_allowed"}\n'
        elif (environ.get('QUERY_STRING') or environ.get('CONTENT_LENGTH', '') not in ('', '0')
              or environ.get('HTTP_TRANSFER_ENCODING')):
            status, body = '400 Bad Request', b'{"status":"parameters_refused"}\n'
        headers = [('Content-Type', 'application/json; charset=utf-8'),
                   ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'),
                   ('X-Content-Type-Options', 'nosniff')]
        if status.startswith('405'):
            headers.append(('Allow', 'GET'))
        start_response(status, headers)
        return [body]

    return app


app = create_app()
