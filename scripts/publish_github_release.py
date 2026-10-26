"""Publish prepared assets using the existing system Git credential, never save it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPO = 'mason2237/YingXu'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream, 'sha256').hexdigest()


class GitHub:
    def __init__(self):
        env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never', 'GIT_TRACE': '0', 'GCM_TRACE': '0'}
        credential = subprocess.run(['git', 'credential', 'fill'],
            input='protocol=https\nhost=github.com\nusername=mason2237\n\n',
            text=True, capture_output=True, env=env, cwd=ROOT)
        values = dict(line.split('=', 1) for line in credential.stdout.splitlines() if '=' in line)
        if credential.returncode or not values.get('password'):
            raise RuntimeError('System GitHub authorization is unavailable; no credentials were printed or saved.')
        self.authorization = 'Bearer ' + values['password']

    def request(self, method, route, data=None, *, optional=False, file=None):
        url = route if route.startswith('https://') else 'https://api.github.com'+route
        if not url.startswith(('https://api.github.com/', 'https://uploads.github.com/')):
            raise RuntimeError('Unexpected GitHub API host')
        headers = {'Authorization': self.authorization, 'Accept': 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'YingXu-release-maintenance'}
        payload = None
        if data is not None:
            payload = json.dumps(data, ensure_ascii=False).encode('utf8');headers['Content-Type'] = 'application/json'
        if file:
            headers.update({'Content-Type': 'application/octet-stream', 'Content-Length': str(file.stat().st_size)})
            payload = file.open('rb')
        try:
            with urlopen(Request(url, data=payload, headers=headers, method=method), timeout=180) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as error:
            if optional and error.code == 404:return None
            raise RuntimeError(f'GitHub API {method} failed with HTTP {error.code}; credentials not included in this error.') from None
        finally:
            if file:payload.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args();api = GitHub()
    user = api.request('GET', '/user')
    if user['login'] != 'mason2237':raise RuntimeError('The selected Git account is not the authorized repository owner.')
    repository = api.request('GET', '/repos/'+REPO)
    if not repository['permissions']['push']:raise RuntimeError('Repository push permission unavailable')
    if args.status:
        releases = api.request('GET', '/repos/'+REPO+'/releases?per_page=10')
        print(json.dumps({'login': user['login'], 'repository': REPO, 'defaultBranch': repository['default_branch'],
                          'releases': [{k:r[k] for k in ('tag_name','draft','prerelease','published_at')} for r in releases]}));return
    if not args.publish or not args.assets or not args.commit:
        raise RuntimeError('Publishing requires prepared assets, the exact public source commit and --publish')
    directory = args.assets.resolve()
    if not directory.is_relative_to((ROOT/'outputs/github-release').resolve()):raise RuntimeError('Unexpected asset directory')
    manifest = json.loads((directory/'RELEASE_MANIFEST.json').read_text(encoding='utf8'))
    version = manifest['version'];tag = 'v'+version
    if not args.commit or len(args.commit) != 40:raise RuntimeError('Expected full public source commit')
    commit = api.request('GET', f'/repos/{REPO}/commits/{args.commit}')
    if commit['sha'] != args.commit:raise RuntimeError('Public commit mismatch')
    candidates = [directory/entry['name'] for entry in manifest['files']] + [directory/'SHA256SUMS.txt']
    for entry in manifest['files']:
        p = directory/entry['name']
        if sha(p) != entry['sha256'] or p.stat().st_size != entry['bytes']:raise RuntimeError('Asset changed: '+p.name)
    body = (directory/'RELEASE_NOTES.md').read_text(encoding='utf8')
    release = api.request('GET', f'/repos/{REPO}/releases/tags/{tag}', optional=True)
    if release is None:
        release = api.request('POST', f'/repos/{REPO}/releases', {
            'tag_name': tag, 'target_commitish': args.commit, 'name': f'映序 {version} · Electron 高刷工作台与在线字幕',
            'body': body, 'draft': True, 'prerelease': True})
    if release['target_commitish'] not in {args.commit, repository['default_branch']}:
        raise RuntimeError('Existing release points to a different target')
    for p in candidates:
        release = api.request('GET', f'/repos/{REPO}/releases/{release["id"]}')
        existing = next((item for item in release['assets'] if item['name'] == p.name), None)
        if existing:
            if existing.get('digest') != 'sha256:'+sha(p) or existing['size'] != p.stat().st_size:
                raise RuntimeError('Existing asset differs; refusing to overwrite: '+p.name)
        else:
            url = release['upload_url'].split('{', 1)[0]+'?'+urlencode({'name': p.name})
            print(json.dumps({'uploading': p.name, 'bytes': p.stat().st_size}), flush=True)
            existing = api.request('POST', url, file=p)
            if existing.get('digest') != 'sha256:'+sha(p) or existing['size'] != p.stat().st_size:
                raise RuntimeError('GitHub upload digest mismatch: '+p.name)
    release = api.request('PATCH', f'/repos/{REPO}/releases/{release["id"]}',
                          {'body': body, 'draft': False, 'prerelease': True})
    result = {'repository': REPO, 'tag': tag, 'publicSourceCommit': args.commit,
              'url': release['html_url'], 'draft': release['draft'], 'prerelease': release['prerelease'],
              'publishedAt': release['published_at'], 'assets': [{k:a[k] for k in ('name','size','digest','state','browser_download_url')} for a in release['assets']]}
    (directory/'PUBLICATION.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:main()
    except Exception as error:
        print(str(error), file=sys.stderr);sys.exit(1)
