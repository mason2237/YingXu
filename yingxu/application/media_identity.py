"""Identity hints are bounded to a selected row; correction never spreads to neighbours."""
from ..domain.media_identity import imdb
from ..domain.matching import episode_identity
from ..domain.review import path_key
from .reviewing import ReviewData


class MediaIdentity:
    def __init__(self,workspace,reader):self.workspace,self.reader=workspace,reader

    def dispatch(self,action,params):
        ws=self.workspace;data=ws.require_review(params);index=data.index(params['rowId']);row=data.review.rows[index]
        if action=='identity.read':
            session=ws.session_id
            def complete(value):
                if ws.session_id!=session or ws.data is not data:
                    from ..domain.errors import ProtocolError
                    raise ProtocolError('STALE_REVIEW','选择或页面已变化，请重新读取。')
                manual=data.review.identities.get(path_key(row.video))
                if manual:
                    value['manual']=manual
                    if any(item['id']!=manual['id'] or item['kind']!=manual['kind'] for item in value['ids']):
                        value['conflict']=True;value['reasons'].append('人工标识与同名 NFO 不同，保留两种来源供核对')
                return value
            return ws.launch('identity',lambda worker:self.reader.read(row.video,include_hash=params.get('includeHash',False),should_stop=worker.stop.is_set),complete,'读取所选视频的本地识别信息…')
        value=imdb(params['imdbId']);kind='episode' if episode_identity(row.video.stem) else 'movie'
        ws.invalidate_preview();ws.invalidate_online()
        def work(worker):
            review=data.review.fork(index);review.identities[path_key(row.video)]={'id':value,'kind':kind,'source':'manual'}
            for match in review.rows[index].matches:match.confirmed=False;match.needs_review=True
            updated=ReviewData(review,data.register,scan_id=data.scan_id,revision=data.revision+1,warnings=data.scan_warnings,recognition=data.recognition)
            return updated,ws.draft_capture(updated,worker.stop.is_set)
        def complete(value):
            ws.draft_publish(value[1]);ws.data=value[0];ws.revision=value[0].revision
            return {'rowId':data.rows[index]['rowId'],'revision':value[0].revision}
        return ws.launch('review',work,complete,'保存当前作品的人工标识，撤回旧确认…')
