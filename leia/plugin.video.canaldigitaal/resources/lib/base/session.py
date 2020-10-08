import json, requests, sys

from resources.lib.base import settings
from resources.lib.base.constants import SESSION_CHUNKSIZE
from resources.lib.base.log import log
from resources.lib.base.util import load_profile, query_settings
from resources.lib.constants import CONST_BASE_HEADERS

try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite

class Session(requests.Session):
    def __init__(self, headers=None, cookies_key=None, save_cookies=True, base_url='{}', timeout=None, attempts=None):
        super(Session, self).__init__()

        profile_settings = load_profile(profile_id=1)
        user_agent = profile_settings['user_agent']
        CONST_BASE_HEADERS.update({'User-Agent': user_agent})

        if headers:
            CONST_BASE_HEADERS.update(headers)

        self._headers = CONST_BASE_HEADERS or {}
        self._cookies_key = cookies_key
        self._save_cookies = save_cookies
        self._base_url = base_url
        self._timeout = timeout or (5, 10)
        self._attempts = attempts or 2

        self.headers.update(self._headers)

        if self._cookies_key:
            try:
                cookies = json.loads(profile_settings[cookies_key])
            except:
                cookies = {}

            self.cookies.update(cookies)

    def request(self, method, url, timeout=None, attempts=None, **kwargs):
        if not url.startswith('http'):
            url = self._base_url.format(url)

        kwargs['timeout'] = timeout or self._timeout
        attempts = attempts or self._attempts

        if sys.version_info < (3, 0):
            rngattempts = range(1, attempts+1)
        else:
            rngattempts = list(range(1, attempts+1))

        for i in rngattempts:
            log.debug('Attempt {}/{}: {} {} {}'.format(i, attempts, method, url, kwargs if method.lower() != 'post' else ""))

            try:
                data = super(Session, self).request(method, url, **kwargs)

                if self._cookies_key and self._save_cookies:
                    self.save_cookies()

                return data
            except:
                if i == attempts:
                    raise

    def save_cookies(self):
        if not self._cookies_key:
            raise Exception('A cookies key needs to be set to save cookies')

        query = "UPDATE `vars` SET `cookies`='{cookies}' WHERE profile_id={profile_id}".format(cookies=json.dumps(self.cookies.get_dict()), profile_id=1)
        query_settings(query=query, return_result=False, return_insert=False, commit=True)

    def clear_cookies(self):
        self.cookies.clear()

    def chunked_dl(self, url, dst_path, method='GET'):
        resp = self.request(method, url, stream=True)
        resp.raise_for_status()

        with open(dst_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=SESSION_CHUNKSIZE):
                f.write(chunk)