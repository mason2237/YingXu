"""Independent interval gates. Scores describe overlap, not success probability."""


def intervals(document):
    values=sorted((c.start,c.end) for c in document.cues if c.kind!='comment' and c.start is not None and c.end is not None and c.end>c.start)
    merged=[]
    for start,end in values:
        if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
        else:merged.append((start,end))
    return merged


def dice(left,right,start,end):
    left=[(max(a,start),min(b,end)) for a,b in left if b>start and a<end]
    right=[(max(a,start),min(b,end)) for a,b in right if b>start and a<end]
    total=sum(b-a for a,b in left)+sum(b-a for a,b in right);overlap=0;i=j=0
    while i<len(left) and j<len(right):
        overlap+=max(0,min(left[i][1],right[j][1])-max(left[i][0],right[j][0]))
        if left[i][1]<right[j][1]:i+=1
        else:j+=1
    return 2*overlap/total if total else 0.


def reference_quality(source,reference):
    left,right=intervals(source),intervals(reference)
    if len(left)<20 or len(right)<20:return {'accepted':False,'reason':'参考与输入至少需要 20 段有效对白，寡对白不能可靠同步。'}
    end=max(left[-1][1],right[-1][1]);start=min(left[0][0],right[0][0])
    if end-start<30000:return {'accepted':False,'reason':'有效时间跨度不足 30 秒。'}
    scores=[dice(left,right,start+(end-start)*i/3,start+(end-start)*(i+1)/3) for i in range(3)]
    global_score=dice(left,right,start,end)
    accepted=global_score>=.65 and min(scores)>=.5
    return {'accepted':accepted,'reason':'三个时间窗口通过重叠核对' if accepted else '分段对照不足，可能是错版本、错参考或对白过少',
            'overlap':round(global_score,4),'windows':[round(v,4) for v in scores]}
