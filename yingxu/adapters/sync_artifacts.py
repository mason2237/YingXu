"""Private transformation candidates. Originals and user directories are read-only here."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from .subtitle_imports import private_path
from .subtitle_reader import read_handle
from ..domain.errors import ProtocolError
from ..domain.review import path_key


class LocalTransforms:
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);private_path(self.root,self.root)

    def directory(self,identifier):
        if not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('无效的处理结果标识')
        path=self.root/identifier;private_path(path,self.root);return path

    def create(self,filename,text,metadata):
        raw=text.encode('utf8')
        if not raw or len(raw)>8*1024*1024 or Path(filename).name!=filename:raise ValueError('处理结果文件名或大小无效。')
        if len(list(self.root.iterdir()))>=64:raise ValueError('处理缓存已满，请释放无引用的旧结果。')
        private_path(self.root,self.root)
        identifier=uuid4().hex;(self.root/identifier).mkdir();directory=self.directory(identifier)
        path=directory/filename
        with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        record={'v':1,'id':identifier,'name':filename,'digest':hashlib.sha256(raw).hexdigest(),'metadata':metadata}
        temporary=directory/'receipt.tmp'
        with temporary.open('x',encoding='utf8') as stream:json.dump(record,stream,ensure_ascii=False,allow_nan=False);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,directory/'receipt.json');return record

    def get(self,identifier):
        path=self.directory(identifier)/'receipt.json'
        with read_handle(path) as stream:raw=stream.read(65537)
        if len(raw)>65536:raise ValueError('处理收据超限')
        value=json.loads(raw)
        if value.get('v')!=1 or value.get('id')!=identifier or Path(value['name']).name!=value['name']:raise ValueError('处理收据无效')
        return value

    def path(self,identifier):
        value=self.get(identifier);path=self.directory(identifier)/value['name'];private_path(path,self.root);return path

    def list(self):
        result=[]
        for path in self.root.iterdir():
            if path.is_dir() and (path/'receipt.json').is_file():
                try:result.append(self.get(path.name))
                except (OSError,ValueError):continue
        return result

    def discard(self,identifier,protected):
        record=self.get(identifier);directory=self.directory(identifier);path=directory/record['name']
        if path_key(path) in {path_key(Path(p)) for p in protected}:raise ProtocolError('CACHE_IN_USE','此结果被审阅、恢复或撤销引用，不能清除。')
        if {p.name for p in directory.iterdir()}-{'receipt.json',record['name']}:raise ValueError('缓存含未知文件，保留待核对。')
        for file in (path,directory/'receipt.json'):
            if file.exists():private_path(file,self.root);file.unlink()
        directory.rmdir();return {'discarded':True}
