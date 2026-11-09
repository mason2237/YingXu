"""Bounded scheduling decisions, with no network, clock or credentials."""
from email.utils import parsedate_to_datetime
import math

KINDS=frozenset({'transient','rate_limited','auth','manual','unsupported','security','permanent'})


def classify(status=None,kind=None):
    if kind in KINDS:return kind
    if status==429:return 'rate_limited'
    if status in {401,403}:return 'auth'
    if type(status) is int and 500<=status<=599:return 'transient'
    return 'permanent'


def retry_delay(kind,attempt,now,retry_after=None,jitter=.5):
    if kind not in {'transient','rate_limited'} or not 0<=attempt<3:return None
    delay=min(60,2**(attempt+1))*(.8+.4*max(0,min(1,jitter)))
    if retry_after is not None:
        try:wait=float(retry_after)
        except (ValueError,TypeError):
            try:wait=parsedate_to_datetime(str(retry_after)).timestamp()-now
            except (ValueError,TypeError,OverflowError):return None
        if not math.isfinite(wait) or wait>86400:return None
        delay=max(delay,max(0,wait))
    return delay


def public_retry(value):
    return {key:value.get(key) for key in ('attempt','nextAttempt','error','paused')}
