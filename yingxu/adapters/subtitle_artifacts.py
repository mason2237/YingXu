"""Durable, private subtitle inbox. Never owns or deletes media-directory files."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
from threading import RLock
from time import time
from uuid import uuid4

from ..domain.errors import ProtocolError
from .http_transfer import transfer, digest
from .legacy_operations import file_mark
from .subtitle_downloads import safe_filename, inspect_download, MAX_DOWNLOAD_BYTES, same_origin_blob
from .subtitle_imports import prepare_download, private_path
from .subtitle_sites.websites import website_for
from .subtitle_sites.zimuku import public_https, source_url


class LocalSubtitleArtifacts:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.root.mkdir(parents=True, exist_ok=True)
        private_path(self.root, self.root)
        self.lock = RLock()
        # Restart records a stopped external effect; it never resumes networking.
        for record in self.list():
            if record['status'] in {'receiving', 'downloading', 'preparing'}:
                self.update(record['id'], status='interrupted', message='上次任务中断；缓存已保留，未自动重试。')

    def directory(self, identifier):
        if len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
            raise ValueError('无效的暂存标识。')
        directory = self.root / identifier
        private_path(directory, self.root)
        return directory

    def get(self, identifier):
        with self.lock:
            path = self.directory(identifier) / 'receipt.json'
            private_path(path, self.root)
            if path.stat().st_size > 256*1024:
                raise ValueError('暂存收据超过限制。')
            record = json.loads(path.read_text(encoding='utf8'))
            if record.get('id') != identifier or record.get('v') != 1:
                raise ValueError('暂存收据身份或版本无效。')
            return record

    def update(self, identifier, **changes):
        with self.lock:
            record = self.get(identifier)
            record.update(changes)
            self._save(record)
            return record

    def _save(self, record):
        directory = self.directory(record['id'])
        temporary = directory / ('receipt-'+uuid4().hex+'.tmp')
        with temporary.open('x', encoding='utf8') as stream:
            json.dump(record, stream, ensure_ascii=False, allow_nan=False)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, directory / 'receipt.json')

    def list(self):
        with self.lock:
            values = []
            for path in self.root.iterdir():
                if path.name.startswith('.'):
                    continue
                if (path / 'receipt.json').exists():
                    values.append(self.get(path.name))
            return sorted(values,key=lambda value:value.get('createdAt',0),reverse=True)

    def reserve(self, offer, association):
        if not isinstance(offer.get('offerId'), str) or len(offer['offerId']) != 32 or any(c not in '0123456789abcdef' for c in offer['offerId']):
            raise ValueError('下载请求标识无效。')
        site = website_for(association['provider'])
        if not source_url(offer['page'], site.hosts):
            raise ValueError('下载页面不属于已确认的字幕来源。')
        url = offer['url']
        blob = same_origin_blob(url, offer['page'], site.hosts)
        if not blob and not public_https(url):
            raise ValueError('不允许的下载来源。')
        if type(offer['total']) is not int or not 0 <= offer['total'] <= MAX_DOWNLOAD_BYTES:
            raise ValueError('下载大小超过 64 MiB。')
        if offer.get('mime', '').split(';')[0] in {'text/html','application/xhtml+xml','application/x-msdownload','application/x-executable'}:
            raise ValueError('网页或程序不能作为字幕下载。')
        with self.lock:
            records = self.list()
            if sum(row['status']!='compacted' for row in records) >= 128 or len(records)>=10000:
                raise ValueError('暂存文件已达 128 份，请先清理无需保留的缓存。')
            used = 0
            for path in self.root.rglob('*'):
                private_path(path, self.root)
                if path.is_file():
                    used += path.stat().st_size
            # Reserve the full transfer plus bounded extraction budget.
            if used+MAX_DOWNLOAD_BYTES+32*1024*1024 > 512*1024*1024:
                raise ValueError('字幕缓存接近 512 MiB，请先清理无需保留的缓存。')
            identifier = uuid4().hex
            (self.root / identifier).mkdir()
            record = {'v': 1, 'id': identifier, 'filename': safe_filename(offer['name']),
                      'url': url, 'page': offer['page'], 'blob': blob, 'total': offer['total'],
                      'status': 'receiving' if blob else 'downloading', 'message': '',
                      'association': association, 'offerId': offer['offerId'], 'imported': False, 'prepared': [], 'http': {}}
            record['createdAt'] = time()
            self._save(record)
            return record

    def path(self, identifier):
        record = self.get(identifier)
        if safe_filename(record['filename']) != record['filename']:
            raise ValueError('暂存文件名无效。')
        path = self.directory(identifier) / record['filename']
        if path.exists():
            private_path(path, self.root)
        return path

    def transfer(self, identifier, stop, report, headers=None):
        record = self.get(identifier)
        if record['blob']:
            raise ValueError('网站生成的 blob 不能跨会话续传，请重新获取。')
        self.update(identifier, status='downloading', message='正在下载')
        return transfer(record, self.path(identifier),
                        lambda http: self.update(identifier, http=http), stop, report, headers)

    def verify(self, identifier):
        record = self.get(identifier)
        if record['blob']:
            temporary = self.root / '.incoming' / (record['offerId']+'.part')
            private_path(temporary, self.root)
            if not 0 < temporary.stat().st_size <= MAX_DOWNLOAD_BYTES:
                raise ValueError('网站生成的下载为空或过大。')
            with temporary.open('rb') as source, self.path(identifier).open('xb') as target:
                size = 0
                while block := source.read(65536):
                    size += len(block)
                    if size > MAX_DOWNLOAD_BYTES:
                        raise ValueError('网站生成的下载超过限制。')
                    target.write(block)
                target.flush(); os.fsync(target.fileno())
            temporary.unlink()
        path = self.path(identifier)
        inspect_download(path)
        with path.open('r+b') as stream:
            os.fsync(stream.fileno())
        value = digest(path)
        record = self.get(identifier)
        if record['http'] and record['http'].get('digest') != value:
            raise ValueError('下载完成后内容发生变化。')
        self.update(identifier, digest=value, status='preparing')
        return value

    def prepare(self, identifier, stop):
        path = self.path(identifier)
        before = self.verify(identifier)
        files, warnings = prepare_download(path, self.root, file_mark(path), should_stop=stop)
        outputs = []
        for item in files:
            private_path(item.path, self.root)
            with item.path.open('r+b') as stream:
                os.fsync(stream.fileno())
            outputs.append({'relative': str(item.path.relative_to(self.directory(identifier))),
                            'name': item.original_name, 'mark': asdict(item.mark), 'digest': digest(item.path)})
        if before != digest(path):
            raise ValueError('解压过程中源文件发生变化。')
        self.update(identifier, status='ready', message='已验证并准备好；等待导入审阅。',
                    prepared=outputs, warnings=warnings[:20])
        return outputs

    def prepared(self, identifier):
        record = self.get(identifier)
        if record['status'] != 'ready':
            raise ValueError('这份下载尚未通过内容检查。')
        values = []
        for output in record['prepared']:
            path = self.directory(identifier) / output['relative']
            private_path(path, self.directory(identifier))
            if asdict(file_mark(path)) != output['mark'] or digest(path) != output['digest']:
                raise ValueError('已验证的字幕发生变化，请重新下载。')
            values.append(path)
        return values

    def discard(self, identifier, protected):
        record = self.get(identifier)
        directory = self.directory(identifier)
        if record['status'] in {'receiving', 'downloading', 'preparing'} or record['imported']:
            raise ProtocolError('CACHE_IN_USE', '活跃任务和已经导入的字幕缓存受保护，不能清除。')
        if any(Path(path).absolute().is_relative_to(directory) for path in protected):
            raise ProtocolError('CACHE_IN_USE', '恢复或撤销日志仍引用此缓存，不能清除。')
        # Validate every member before recursive removal, including junctions.
        for path in directory.rglob('*'):
            private_path(path, self.root)
        incoming = self.root / '.incoming' / (record['offerId']+'.part')
        if incoming.exists():
            private_path(incoming, self.root / '.incoming')
            incoming.unlink()
        shutil.rmtree(directory)
        return {'discarded': True}

    def maintenance_due(self, now=None):
        cutoff=(time() if now is None else now)-30*86400
        return any(row['imported'] and row['status']=='ready' and 0<row.get('createdAt',0)<cutoff for row in self.list())

    def compact(self, identifier, protected, stop=lambda:False):
        """Remove only verified, unreferenced payloads; retain directory identities.

        Undo may require an empty prepared directory with its original file ID.
        Keeping that skeleton also avoids deleting the operation journal's parents.
        """
        from ..domain.matching import check_cancelled
        from .windows_files import WindowsFile
        record=self.get(identifier)
        if not record['imported'] or record['status'] not in {'ready','compacted'}:
            raise ProtocolError('CACHE_IN_USE','只有已完成导入的缓存可以释放可回收文件。')
        pinned={os.path.normcase(os.path.abspath(path)) for path in protected}
        candidates=[(self.path(identifier),record.get('digest'))]
        candidates += [(self.directory(identifier)/item['relative'],item['digest']) for item in record['prepared']]
        released=0;kept=0
        for path,expected in candidates:
            check_cancelled(stop)
            if not path.exists():continue
            if os.path.normcase(os.path.abspath(path)) in pinned:
                kept+=1;continue
            private_path(path,self.directory(identifier))
            if os.name=='nt':
                with WindowsFile(path,delete=True) as handle:
                    version=handle.version(should_stop=stop)
                    if not expected or version['digest']!=expected:
                        kept+=1;continue
                    handle.remove();released+=version['size']
            else:
                if not expected or digest(path)!=expected:
                    kept+=1;continue
                released+=path.stat().st_size;path.unlink()
        self.update(identifier,status='compacted',releasedBytes=record.get('releasedBytes',0)+released,
                    message=f'已释放可回收文件；{kept} 份被引用或已变化的文件保留，撤销目录完整。')
        return {'releasedBytes':released,'protectedFiles':kept}

    def maintain(self, protected, stop=lambda:False, now=None):
        cutoff=(time() if now is None else now)-30*86400
        total=0
        for row in self.list():
            if row['imported'] and row['status']=='ready' and 0<row.get('createdAt',0)<cutoff:
                total+=self.compact(row['id'],protected,stop)['releasedBytes']
        return {'releasedBytes':total}
