"""Bounded HTTP transfer with validator-bound Range resume, never blind append."""
import hashlib
import http.client
import os
from pathlib import Path
import re
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..domain.matching import check_cancelled
from .subtitle_downloads import MAX_DOWNLOAD_BYTES
from .subtitle_sites.zimuku import public_https


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if not public_https(newurl):
            raise ValueError('下载跳转到不允许的网址。')
        result = super().redirect_request(request, fp, code, message, headers, newurl)
        if urlsplit(newurl).netloc != urlsplit(request.full_url).netloc:
            result.remove_header('Cookie')
            result.remove_header('Authorization')
        return result


def transfer(record, path, save, stop, report, headers=None, *, opener=None):
    """save() persists checkpoints only after fsync. A crash tail is discarded.

    A strong ETag or Last-Modified plus stable total size binds partial bytes.
    Without a validator, retry starts a fresh bounded request. 416 always restarts;
    it is never accepted as proof that the previous file was complete.
    """
    if opener is None and not public_https(record['url']):
        raise ValueError('仅允许公共 HTTPS 下载。')
    opener = opener or build_opener(SafeRedirect())
    path = Path(path)
    state = dict(record.get('http') or {})
    offset = state.get('offset', 0)
    if offset and (not path.is_file() or path.stat().st_size < offset):
        raise ValueError('续传缓冲缺失或变短，不能拼接。')
    if offset:
        with path.open('r+b') as stream:
            stream.truncate(offset)
            stream.flush(); os.fsync(stream.fileno())
        if digest(path) != state.get('digest'):
            raise ValueError('续传缓冲内容已变化，不能拼接。')
    validator = state.get('etag') or state.get('modified')
    if not validator:
        offset = 0
    base = {'Accept-Encoding': 'identity', 'User-Agent': 'YingXu/0.10'}
    for key, value in (headers or {}).items():
        if key not in {'Cookie', 'Referer', 'User-Agent'} or not isinstance(value, str) or len(value) > 2048 or '\r' in value or '\n' in value:
            raise ValueError('下载请求头无效。')
        base[key] = value
    for attempt in range(2):
        check_cancelled(stop)
        request_headers = dict(base)
        if offset:
            request_headers.update(Range=f'bytes={offset}-', **{'If-Range': validator})
        try:
            response = opener.open(Request(record['url'], headers=request_headers), timeout=15)
        except HTTPError as error:
            if error.code == 416 and offset and attempt == 0:
                error.close(); offset = 0; continue
            code = error.code; error.close()
            raise ValueError('下载链接已过期或需网站验证，请回到原网站重新获取。' if code in {401,403,404,410} else f'下载服务器返回 HTTP {code}。') from None
        with response:
            status = response.status
            if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                raise ValueError('下载编码不支持安全续传。')
            mime = response.headers.get_content_type()
            if mime in {'text/html', 'application/xhtml+xml', 'application/x-msdownload', 'application/x-executable'}:
                raise ValueError('下载返回了网页或程序，已拒绝。')
            etag = response.headers.get('ETag', '')
            if etag.startswith('W/') or not re.fullmatch(r'"[^\r\n]{1,240}"', etag):
                etag = ''
            modified = response.headers.get('Last-Modified', '')[:100]
            try:
                parsedate_to_datetime(modified)
            except (ValueError, TypeError):
                modified = ''
            final_url = response.geturl()
            length = response.headers.get('Content-Length')
            length = int(length) if length is not None else None
            if status == 206:
                match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                if not offset or not match:
                    raise ValueError('服务器返回无效的续传区间。')
                start, end, total = map(int, match.groups())
                same = etag == state.get('etag') if state.get('etag') else modified == state.get('modified')
                if not same or total != state.get('total') or final_url != state.get('url', record['url']):
                    if attempt == 0:
                        offset = 0; continue
                    raise ValueError('远端下载对象已变化。')
                if start != offset or end != total-1 or end < start or length != total-offset:
                    raise ValueError('续传区间或长度不一致，未拼接。')
            elif status == 200:
                offset, total = 0, length
            else:
                raise ValueError(f'未支持的下载响应 HTTP {status}。')
            if total is not None and not 0 < total <= MAX_DOWNLOAD_BYTES:
                raise ValueError('下载为空或超过 64 MiB。')
            state = {'offset': offset, 'etag': etag, 'modified': modified, 'total': total, 'url': final_url}
            with path.open('r+b' if offset else 'wb') as output:
                output.seek(offset)
                received, checkpoint = offset, offset
                def persist():
                    output.flush(); os.fsync(output.fileno())
                    state.update(offset=received, digest=digest(path))
                    save(dict(state))
                persist()
                try:
                    while True:
                        check_cancelled(stop)
                        try:
                            block = response.read(64*1024)
                        except http.client.IncompleteRead as error:
                            block = error.partial
                            if block and received+len(block) <= MAX_DOWNLOAD_BYTES:
                                output.write(block); received += len(block)
                            raise ValueError('下载中断；已保存的有效字节可在重试时核对。') from error
                        if not block:
                            break
                        if received+len(block) > MAX_DOWNLOAD_BYTES or (total is not None and received+len(block) > total):
                            raise ValueError('下载超过声明长度或限制。')
                        output.write(block); received += len(block)
                        report(received, total, '正在下载字幕…', 'download')
                        if received-checkpoint >= 1024*1024:
                            persist(); checkpoint = received
                    if total is not None and received != total:
                        raise ValueError('下载尚未完整；有效缓冲已保留。')
                    if not received:
                        raise ValueError('下载为空。')
                    check_cancelled(stop)
                finally:
                    persist()
            return {'size': received, 'digest': state['digest'], 'resumed': offset > 0}
    raise ValueError('下载对象不能安全续传，请重新取得链接。')
