"""Zimuku website adapter. Discover the actual form; do not guess a search API."""
import ipaddress
import json
from pathlib import PureWindowsPath
import re
import unicodedata
from urllib.parse import urlsplit

from .websites import ZIMUKU_HOSTS

HOME_URL = "https://zimuku.org/"
SITE_HOSTS = ZIMUKU_HOSTS


def public_https(url):
    """Restrict the browser to HTTPS, excluding explicit local/network addresses.

    This is a URL filter, not a DNS-rebinding firewall. Chromium retains its
    network isolation and permission checks; the remote page has no native API.
    """
    try:
        value = urlsplit(url)
        host = value.hostname or ""
        if (value.scheme != "https" or value.username or value.password
                or value.port not in (None, 443) or not host
                or any(char in url for char in "\\\r\n\t")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return ("." in host and not host.endswith((".", ".local", ".localhost", ".internal"))
                    and not re.fullmatch(r"[0-9.]+|0x[0-9a-f]+", host, re.I))
    except ValueError:
        return False


def source_url(url, hosts=SITE_HOSTS):
    return public_https(url) and urlsplit(url).hostname in hosts


def search_terms(filename):
    """Default to a title, leaving release/year/episode details for local ranking."""
    name = PureWindowsPath(filename).stem
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"(?i)(?:www\.)[a-z0-9-]+\.(?:com|net|org|tv|cn)(?:\.cn)?", " ", name)
    noise = r"(?i)\b(?:\d{3,4}p|4k|8k|webrip|web[- ]?dl|blu[- ]?ray|[xh]26[45]|hevc|aac|dts|subsplease|dbd[- ]raws|yts|rarbg|cmct|chd)\b|字幕|中字|国语|双语|内封|简繁|简中|繁中|人人影视|电影天堂|阳光电影|高清"
    outside = re.sub(r"[\[【(（][^\]】)）]*[\]】)）]", "", name).lstrip(' ._-')
    bracket_title = not outside or bool(re.match(r'(?:19|20)\d{2}|\d{3,4}p',outside,re.I))
    def bracket(match):
        value = match.group(1).strip()
        if re.search(noise, value) or re.fullmatch(r"(?:19|20)\d{2}|\d{1,3}|(?i:S\d+E?\d*)", value):
            return " "
        return " " + value + " " if bracket_title or re.search(r"[\u3400-\u9fff]", value) else " "
    name = re.sub(r"[\[【(（]([^\]】)）]*)[\]】)）]", bracket, name)
    name = re.sub(r"[._]+", " ", name)
    markers = [match.start() for match in re.finditer(
        r"(?i)(?<![A-Za-z0-9])(?:\d{3,4}[pi]|4k|8k|web[ -]?(?:dl|rip)|blu[ -]?ray|b[dr]rip|hdtv|remux|[xh][ .-]?26[45]|hevc|av1|aac|dts|S\d{1,2}(?:E\d{1,3})?|E(?:P)?\d{1,3}|\d{1,2}x\d{1,3}|国语|双语|中字)(?!\w)|第[零一二三四五六七八九十百\d]+[季集话話]|\s+-\s+\d{1,3}(?:\s|$)", name)]
    # Numeric movie titles such as 1917/1984 remain valid at the beginning.
    markers += [m.start() for m in re.finditer(r"(?<!\d)(?:19|20)\d{2}(?!\d)", name) if name[:m.start()].strip(" -")]
    if markers: name = name[:min(markers)]
    name = " ".join(name.strip(" -–—").split())
    # Prefer one Chinese title over concatenated Chinese + English aliases.
    if re.search(r"[\u3400-\u9fff]", name):
        name = re.split(r"\s+(?=[A-Za-z][A-Za-z '\-]+$)", name, maxsplit=1)[0]
    return name[:200]


def verification_script():
    """Recognize a website challenge, without reading or answering its CAPTCHA."""
    return r"""(() => {
      const text = (document.title + ' ' + (document.body?.innerText || '').slice(0,1800));
      return /网站访问认证|请输入验证码.{0,24}继续访问|人机验证|verify.{0,20}(human|yourself)|checking your browser/i.test(text);
    })()"""


def submit_search_script(query, hosts=SITE_HOSTS):
    """Fill exactly one visible search form on the current trusted site.

    Both the document and form destination are checked. This is best-effort DOM
    adaptation, not a verified Zimuku endpoint. No cookies or hidden tokens are
    returned to Python. Challenges and ambiguous forms stay under user control.
    """
    payload = json.dumps({"query": query, "hosts": sorted(hosts)}, ensure_ascii=True)
    return r"""(() => {
      const config = PAYLOAD;
      const allowed = value => {
        try {
          const u = new URL(value, location.href);
          return u.protocol === 'https:' && config.hosts.includes(u.hostname)
            && (!u.port || u.port === '443') && !u.username && !u.password;
        } catch { return false; }
      };
      if (!allowed(location.href)) return {status:'untrusted'};
      const candidates = [];
      for (const form of document.forms) {
        if (!allowed(form.action || location.href)
            || !['get','post'].includes(form.method.toLowerCase())) continue;
        for (const input of form.querySelectorAll('input')) {
          if (input.disabled || !input.name || !['search','text'].includes(input.type)
              || !input.getClientRects().length) continue;
          if (input.type === 'search' || /^(q|keyword|keywords|search|searchword|wd|key)$/i.test(input.name))
            candidates.push({form,input});
        }
      }
      if (candidates.length !== 1)
        return {status:candidates.length ? 'ambiguous' : 'no_form', count:candidates.length};
      const {form,input} = candidates[0];
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,config.query);
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
      HTMLFormElement.prototype.requestSubmit.call(form);
      return {status:'submitted'};
    })()""".replace("PAYLOAD", payload)
