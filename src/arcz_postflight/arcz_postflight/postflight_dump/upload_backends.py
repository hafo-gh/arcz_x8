"""Resumable upload backends (stdlib only).

The recommended backend implements the **tus 1.0** resumable protocol
(https://tus.io). tus is the standard choice for interruptible uploads over
plain HTTP(S): it survives power loss, dropped LTE links and NAT/proxies, and
gives the server side a well-defined spec to implement.

Protocol summary (what the separately-developed server must support):

  Creation:  POST  <endpoint>
             Tus-Resumable: 1.0.0
             Upload-Length: <total-bytes>
             Upload-Metadata: filename <base64>
             -> 201 Created, Location: <upload-url>

  Offset:    HEAD  <upload-url>
             Tus-Resumable: 1.0.0
             -> 200/204, Upload-Offset: <bytes-server-has>

  Data:      PATCH <upload-url>
             Tus-Resumable: 1.0.0
             Upload-Offset: <current-offset>
             Content-Type: application/offset+octet-stream
             <chunk bytes>
             -> 204, Upload-Offset: <new-offset>

The ``put_range`` backend is a minimal fallback for servers that only accept a
single Content-Range PUT.
"""
import base64
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

TUS_VERSION = '1.0.0'


class UploadError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status

    @property
    def terminal(self):
        return self.status in {
            400, 401, 403, 404, 409, 410, 412, 413, 415, 422,
        }


def _auth_headers(config):
    token = config.get('upload.auth_token')
    token_env = config.get('upload.auth_token_env')
    if not token and token_env:
        token = os.environ.get(token_env)
    return {'Authorization': 'Bearer %s' % token} if token else {}


def _request(url, method, headers=None, data=None, timeout=60):
    req = Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        return urlopen(req, timeout=timeout)
    except HTTPError as exc:
        try:
            detail = exc.read(2048).decode('utf-8', errors='replace')
        except Exception:
            detail = ''
        message = '%s %s -> HTTP %s: %s' % (
            method, url, exc.code, exc.reason)
        if detail:
            message += ' (%s)' % detail.strip()
        raise UploadError(message, status=exc.code)
    except URLError as exc:
        raise UploadError('%s %s -> %s' % (method, url, exc.reason))


def _tus_create(config, record):
    endpoint = config.get('upload.endpoint')
    filename = os.path.basename(record['zip_path'])
    metadata = {
        'filename': filename,
        'vehicle_id': config.vehicle_id,
        'flight_id': record['flight_uuid'],
        'sha256': record['sha256'],
    }
    encoded_metadata = ','.join(
        '%s %s' % (
            key,
            base64.b64encode(value.encode('utf-8')).decode('ascii'),
        )
        for key, value in metadata.items()
    )
    headers = {
        'Tus-Resumable': TUS_VERSION,
        'Upload-Length': str(record['size']),
        'Upload-Metadata': encoded_metadata,
        'Content-Length': '0',
    }
    headers.update(_auth_headers(config))
    resp = _request(endpoint, 'POST', headers=headers, data=b'')
    location = resp.headers.get('Location')
    if not location:
        raise UploadError('tus creation returned no Location header')
    return urljoin(endpoint if endpoint.endswith('/') else endpoint + '/', location)


def _tus_offset(config, upload_url):
    headers = {'Tus-Resumable': TUS_VERSION}
    headers.update(_auth_headers(config))
    resp = _request(upload_url, 'HEAD', headers=headers)
    raw = resp.headers.get('Upload-Offset')
    if raw is None:
        raise UploadError('tus HEAD returned no Upload-Offset header')
    return int(raw)


def upload_tus(config, record, progress_cb, should_continue):
    """Resumable tus upload. ``progress_cb(offset, upload_url)`` persists state."""
    upload_url = record.get('upload_url')
    if not upload_url:
        upload_url = _tus_create(config, record)
        progress_cb(0, upload_url)

    # Trust the server's offset (authoritative) so we resume exactly.
    offset = _tus_offset(config, upload_url)
    progress_cb(offset, upload_url)

    size = record['size']
    chunk_size = int(config.get('upload.chunk_size'))
    headers_base = {'Tus-Resumable': TUS_VERSION,
                    'Content-Type': 'application/offset+octet-stream'}
    headers_base.update(_auth_headers(config))

    with open(record['zip_path'], 'rb') as handle:
        handle.seek(offset)
        while offset < size:
            if not should_continue():
                raise UploadError('upload aborted (shutdown/offline)')
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            headers = dict(headers_base)
            headers['Upload-Offset'] = str(offset)
            headers['Content-Length'] = str(len(chunk))
            resp = _request(upload_url, 'PATCH', headers=headers, data=chunk)
            new_offset = resp.headers.get('Upload-Offset')
            offset = int(new_offset) if new_offset is not None else offset + len(chunk)
            progress_cb(offset, upload_url)

    if offset < size:
        raise UploadError('upload ended early at %d/%d bytes' % (offset, size))
    return offset


def upload_put_range(config, record, progress_cb, should_continue):
    """Fallback: single Content-Range PUT from the last known offset."""
    endpoint = config.get('upload.endpoint')
    filename = os.path.basename(record['zip_path'])
    url = urljoin(endpoint if endpoint.endswith('/') else endpoint + '/', filename)
    size = record['size']
    offset = int(record.get('offset') or 0)
    headers = {
        'Content-Range': 'bytes %d-%d/%d' % (offset, size - 1, size),
        'Content-Length': str(size - offset),
    }
    headers.update(_auth_headers(config))
    with open(record['zip_path'], 'rb') as handle:
        handle.seek(offset)
        data = handle.read()
    if not should_continue():
        raise UploadError('upload aborted (shutdown/offline)')
    _request(url, 'PUT', headers=headers, data=data, timeout=600)
    progress_cb(size, url)
    return size


BACKENDS = {
    'tus': upload_tus,
    'put_range': upload_put_range,
}


def get_backend(name):
    if name not in BACKENDS:
        raise UploadError('unknown upload protocol: %r' % name)
    return BACKENDS[name]
