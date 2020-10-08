import os, time, xbmc

from resources.lib.base import gui, settings
from resources.lib.base.constants import ADDON_ID, ADDON_PROFILE
from resources.lib.base.exceptions import Error
from resources.lib.base.log import log
from resources.lib.base.session import Session
from resources.lib.base.util import check_key, clean_filename, combine_playlist, find_highest_bandwidth, get_credentials, is_file_older_than_x_minutes, load_file, load_prefs, load_profile, load_tests, query_epg, query_settings, set_credentials, update_prefs, write_file
from resources.lib.constants import CONST_BASE_HEADERS, CONST_IMAGE_URL
from resources.lib.language import _

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

try:
    unicode
except NameError:
    unicode = str

try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite

class APIError(Error):
    pass

class API(object):
    def login(self):
        creds = get_credentials()
        username = creds['username']
        password = creds['password']

        query = "UPDATE `vars` SET `cookies`='' WHERE profile_id={profile_id}".format(profile_id=1)
        query_settings(query=query, return_result=False, return_insert=False, commit=True)

        profile_settings = load_profile(profile_id=1)

        session_url = '{api_url}/USER/SESSIONS/'.format(api_url=profile_settings['api_url'])

        email_or_pin = settings.getBool(key='email_instead_of_customer')

        if email_or_pin:
            session_post_data = {
                "credentialsExtAuth": {
                    'credentials': {
                        'loginType': 'UsernamePassword',
                        'username': username,
                        'password': password,
                        'appId': 'KPN',
                    },
                    'remember': 'Y',
                    'deviceInfo': {
                        'deviceId': profile_settings['devicekey'],
                        'deviceIdType': 'DEVICEID',
                        'deviceType' : 'PCTV',
                        'deviceVendor' : profile_settings['browser_name'],
                        'deviceModel' : profile_settings['browser_version'],
                        'deviceFirmVersion' : profile_settings['os_name'],
                        'appVersion' : profile_settings['os_version']
                    }
                },
            }
        else:
            session_post_data = {
                "credentialsStdAuth": {
                    'username': username,
                    'password': password,
                    'remember': 'Y',
                    'deviceRegistrationData': {
                        'deviceId': profile_settings['devicekey'],
                        'accountDeviceIdType': 'DEVICEID',
                        'deviceType' : 'PCTV',
                        'vendor' : profile_settings['browser_name'],
                        'model' : profile_settings['browser_version'],
                        'deviceFirmVersion' : profile_settings['os_name'],
                        'appVersion' : profile_settings['os_version']
                    }
                },
            }

        download = self.download(url=session_url, type='post', headers=None, data=session_post_data, json_data=True, return_json=True)
        data = download['data']
        resp = download['resp']

        if not resp or not resp.status_code == 200 or not data or not check_key(data, 'resultCode') or not data['resultCode'] == 'OK':
            if not data:
                data = {}

            return { 'data': data, 'result': False }

        return { 'data': data, 'result': True }

    #def get_channels_for_user(self):
    #    profile_settings = load_profile(profile_id=1)

    #    channels_url = '{api_url}/TRAY/LIVECHANNELS?orderBy=orderId&sortOrder=asc&from=0&to=999&dfilter_channels=subscription'.format(api_url=profile_settings['api_url'])

    #    download = self.download(url=channels_url, type='get', headers=None, data=None, json_data=False, return_json=True)
    #    data = download['data']
    #    resp = download['resp']

    #    if not resp or not resp.status_code == 200 or not data or not check_key(data['resultObj'], 'containers'):
    #        if not data:
    #            data = {}

    #        return { 'data': data, 'result': False }

    #    return { 'data': data, 'result': True }

    def get_session(self):
        profile_settings = load_profile(profile_id=1)

        devices_url = '{api_url}/USER/DEVICES'.format(api_url=profile_settings['api_url'])

        download = self.download(url=devices_url, type='get', headers=None, data=None, json_data=False, return_json=True)
        data = download['data']
        resp = download['resp']

        if not resp or not resp.status_code == 200 or not data or not check_key(data, 'resultCode') or not data['resultCode'] == 'OK':
            login_result = self.login()

            if not login_result['result']:
                return False

        return True

    def test_channels(self, tested=False, channel=None):
        profile_settings = load_profile(profile_id=1)

        if channel:
            channel = unicode(channel)

        try:
            if not profile_settings['last_login_success'] == 1 or not settings.getBool(key='run_tests'):
                return 5

            query = "UPDATE `vars` SET `test_running`={test_running} WHERE profile_id={profile_id}".format(test_running=1,profile_id=1)
            query_settings(query=query, return_result=False, return_insert=False, commit=True)

            query = "SELECT * FROM `channels`"
            channels = query_epg(query=query, return_result=True, return_insert=False, commit=False)
            results = load_tests(profile_id=1)

            count = 0
            first = True
            last_tested_found = False
            test_run = False
            user_agent = profile_settings['user_agent']

            if not results:
                results = {}

            for row in channels:
                if count == 5 or (count == 1 and tested):
                    if test_run:
                        update_prefs()

                    query = "UPDATE `vars` SET `test_running`={test_running} WHERE profile_id={profile_id}".format(test_running=0,profile_id=1)
                    query_settings(query=query, return_result=False, return_insert=False, commit=True)
                    return count

                id = unicode(row['id'])

                if len(id) > 0:
                    if channel:
                        if not id == channel:
                            continue
                    elif tested:
                        if unicode(profile_settings['last_tested']) == id:
                            last_tested_found = True
                            continue
                        elif last_tested_found:
                            pass
                        else:
                            continue

                    if check_key(results, id) and not tested and not first:
                        continue

                    livebandwidth = 0
                    replaybandwidth = 0
                    live = 0
                    replay = 0
                    epg = 0
                    guide = 0

                    profile_settings = load_profile(profile_id=1)

                    if profile_settings['last_playing'] > int(time.time() - 300):
                        if test_run:
                            update_prefs()

                        query = "UPDATE `vars` SET `test_running`={test_running} WHERE profile_id={profile_id}".format(test_running=0,profile_id=1)
                        query_settings(query=query, return_result=False, return_insert=False, commit=True)
                        return 5

                    playdata = self.play_url(type='channel', channel=id, id=row['assetid'], test=True)

                    if first and not profile_settings['last_login_success']:
                        if test_run:
                            update_prefs()

                        query = "UPDATE `vars` SET `test_running`={test_running} WHERE profile_id={profile_id}".format(test_running=0,profile_id=1)
                        query_settings(query=query, return_result=False, return_insert=False, commit=True)
                        return 5

                    if len(playdata['path']) > 0:
                        CDMHEADERS = CONST_BASE_HEADERS
                        CDMHEADERS['User-Agent'] = user_agent
                        playdata['path'] = playdata['path'].split("&", 1)[0]
                        session = Session(headers=CDMHEADERS)
                        resp = session.get(playdata['path'])

                        if resp.status_code == 200:
                            livebandwidth = find_highest_bandwidth(xml=resp.text)
                            live = 1

                    if check_key(results, id) and first and not tested:
                        first = False

                        if live == 1:
                            continue
                        else:
                            if test_run:
                                update_prefs()

                            query = "UPDATE `vars` SET `test_running`={test_running} WHERE profile_id={profile_id}".format(test_running=0,profile_id=1)
                            query_settings(query=query, return_result=False, return_insert=False, commit=True)
                            return 5

                    first = False
                    counter = 0

                    while not self._abortRequested and not xbmc.Monitor().abortRequested() and counter < 5:
                        if self._abortRequested or xbmc.Monitor().waitForAbort(1):
                            self._abortRequested = True
                            break

                        counter += 1

                        profile_settings = load_profile(profile_id=1)

                        if profile_settings['last_playing'] > int(time.time() - 300):
                            if test_run:
                                update_prefs()

                            query = "UPDATE `vars` SET `test_running`={test_running} WHERE profile_id={profile_id}".format(test_running=0,profile_id=1)
                            query_settings(query=query, return_result=False, return_insert=False, commit=True)
                            return 5

                    if self._abortRequested or xbmc.Monitor().abortRequested():
                        return 5

                    program_url = '{api_url}/TRAY/AVA/TRENDING/YESTERDAY?maxResults=1&filter_channelIds={channel}'.format(api_url=profile_settings['api_url'], channel=channeldata['channel_id'])
                    download = self.download(url=program_url, type='get', headers=None, data=None, json_data=False, return_json=True)
                    data = download['data']
                    resp = download['resp']

                    if resp and resp.status_code == 200 and data and check_key(data, 'resultCode') and data['resultCode'] == 'OK' and check_key(data, 'resultObj') and check_key(data['resultObj'], 'containers') and check_key(data['resultObj']['containers'][0], 'id'):
                        profile_settings = load_profile(profile_id=1)

                        if profile_settings['last_playing'] > int(time.time() - 300):
                            if test_run:
                                update_prefs()

                            query = "UPDATE `vars` SET `test_running`={test_running} WHERE profile_id={profile_id}".format(test_running=0,profile_id=1)
                            query_settings(query=query, return_result=False, return_insert=False, commit=True)
                            return 5

                        playdata = self.play_url(type='program', channel=id, id=data['resultObj']['containers'][0]['id'], test=True)

                        if len(playdata['path']) > 0:
                            CDMHEADERS = CONST_BASE_HEADERS
                            CDMHEADERS['User-Agent'] = user_agent
                            playdata['path'] = playdata['path'].split("&min_bitrate", 1)[0]
                            session = Session(headers=CDMHEADERS)
                            resp = session.get(playdata['path'])

                            if resp.status_code == 200:
                                replaybandwidth = find_highest_bandwidth(xml=resp.text)
                                replay = 1

                    query = "SELECT id FROM `epg` WHERE channel='{channel}' LIMIT 1".format(channel=id)
                    data = query_epg(query=query, return_result=True, return_insert=False, commit=False)

                    if len(data) > 0:
                        guide = 1

                        if live == 1:
                            epg = 1

                    if not self._abortRequested:
                        query = "UPDATE `vars` SET `last_tested`='{last_tested}' WHERE profile_id={profile_id}".format(last_tested=id,profile_id=1)
                        query_settings(query=query, return_result=False, return_insert=False, commit=True)

                        query = "REPLACE INTO `tests_{profile_id}` VALUES ('{id}', '{live}', '{livebandwidth}', '{replay}', '{replaybandwidth}', '{epg}', '{guide}')".format(profile_id=1, id=id, live=live, livebandwidth=livebandwidth, replay=replay, replaybandwidth=replaybandwidth, epg=epg, guide=guide)
                        query_settings(query=query, return_result=False, return_insert=False, commit=True)

                    test_run = True
                    counter = 0

                    while not self._abortRequested and not xbmc.Monitor().abortRequested() and counter < 15:
                        if self._abortRequested or xbmc.Monitor().waitForAbort(1):
                            self._abortRequested = True
                            break

                        counter += 1

                        profile_settings = load_profile(profile_id=1)

                        if profile_settings['last_playing'] > int(time.time() - 300):
                            if test_run:
                                update_prefs()

                            query = "UPDATE `vars` SET `test_running`={test_running} WHERE profile_id={profile_id}".format(test_running=0,profile_id=1)
                            query_settings(query=query, return_result=False, return_insert=False, commit=True)
                            return 5

                    if self._abortRequested or xbmc.Monitor().abortRequested():
                        return 5

                    count += 1
        except:
            if test_run:
                update_prefs()

            count = 5

        query = "UPDATE `vars` SET `test_running`={test_running} WHERE profile_id={profile_id}".format(test_running=0,profile_id=1)
        query_settings(query=query, return_result=False, return_insert=False, commit=True)

        return count

    def play_url(self, type, channel=None, id=None, test=False, from_beginning=False):
        if not self.get_session():
            return None

        profile_settings = load_profile(profile_id=1)
        playdata = {'path': '', 'license': '', 'token': '', 'type': '', 'info': ''}

        license = ''
        asset_id = ''
        militime = int(time.time() * 1000)
        typestr = 'PROGRAM'
        info = []
        program_id = None

        if not test:
            counter = 0

            while not self._abortRequested and not xbmc.Monitor().abortRequested() and counter < 5:
                profile_settings = load_profile(profile_id=1)

                if profile_settings['test_running'] == 0:
                    break

                counter += 1

                query = "UPDATE `vars` SET `last_playing`={last_playing} WHERE profile_id={profile_id}".format(last_playing=int(time.time()),profile_id=1)
                query_settings(query=query, return_result=False, return_insert=False, commit=True)

                if self._abortRequested or xbmc.Monitor().waitForAbort(1):
                    self._abortRequested = True
                    break

            if self._abortRequested or xbmc.Monitor().abortRequested():
                return playdata

        if type == 'channel':
            if not test:
                info_url = '{api_url}/TRAY/SEARCH/LIVE?maxResults=1&filter_airingTime=now&filter_channelIds={channel}&orderBy=airingStartTime&sortOrder=desc'.format(api_url=profile_settings['api_url'], channel=channel)
                download = self.download(url=info_url, type='get', headers=None, data=None, json_data=False, return_json=True)
                data = download['data']
                resp = download['resp']

                if not resp or not resp.status_code == 200 or not data or not check_key(data, 'resultCode') or not data['resultCode'] == 'OK' or not check_key(data, 'resultObj') or not check_key(data['resultObj'], 'containers'):
                    return playdata

                for row in data['resultObj']['containers']:
                    program_id = row['id']

                info = data

            play_url = '{api_url}/CONTENT/VIDEOURL/LIVE/{channel}/{id}/?deviceId={device_key}&profile=G02&time={time}'.format(api_url=profile_settings['api_url'], channel=channel, id=id, device_key=profile_settings['devicekey'], time=militime)
        else:
            if type == 'program':
                typestr = "PROGRAM"
            else:
                typestr = "VOD"

            program_id = id

            program_url = '{api_url}/CONTENT/USERDATA/{type}/{id}'.format(api_url=profile_settings['api_url'], type=typestr, id=id)
            download = self.download(url=program_url, type='get', headers=None, data=None, json_data=False, return_json=True)
            data = download['data']
            resp = download['resp']

            if not resp or not resp.status_code == 200 or not data or not check_key(data, 'resultCode') or not data['resultCode'] == 'OK' or not check_key(data, 'resultObj') or not check_key(data['resultObj'], 'containers'):
                return playdata

            for row in data['resultObj']['containers']:
                if check_key(row, 'entitlement') and check_key(row['entitlement'], 'assets'):
                    for asset in row['entitlement']['assets']:
                        if type == 'program':
                            if check_key(asset, 'videoType') and check_key(asset, 'programType') and asset['videoType'] == 'SD_DASH_PR' and asset['programType'] == 'CUTV':
                                asset_id = asset['assetId']
                                break
                        else:
                            if check_key(asset, 'videoType') and check_key(asset, 'assetType') and asset['videoType'] == 'SD_DASH_PR' and asset['assetType'] == 'MASTER':
                                if check_key(asset, 'rights') and asset['rights'] == 'buy':
                                    gui.ok(message=_.NO_STREAM_AUTH, heading=_.PLAY_ERROR)
                                    return playdata

                                asset_id = asset['assetId']
                                break

            if len(unicode(asset_id)) == 0:
                return playdata

            play_url = '{api_url}/CONTENT/VIDEOURL/{type}/{id}/{asset_id}/?deviceId={device_key}&profile=G02&time={time}'.format(api_url=profile_settings['api_url'], type=typestr, id=id, asset_id=asset_id, device_key=profile_settings['devicekey'], time=militime)

        if self._abortRequested or xbmc.Monitor().abortRequested():
            return playdata

        if program_id and not test:
            info_url = '{api_url}/CONTENT/DETAIL/{type}/{id}'.format(api_url=profile_settings['api_url'], type=typestr, id=program_id)
            download = self.download(url=info_url, type='get', headers=None, data=None, json_data=False, return_json=True)
            data = download['data']
            resp = download['resp']

            if not resp or not resp.status_code == 200 or not data or not check_key(data, 'resultCode') or not data['resultCode'] == 'OK' or not check_key(data, 'resultObj') or not check_key(data['resultObj'], 'containers'):
                return playdata

            info = data

        if self._abortRequested or xbmc.Monitor().waitForAbort(1):
            return playdata

        download = self.download(url=play_url, type='get', headers=None, data=None, json_data=False, return_json=True)
        data = download['data']
        resp = download['resp']

        if not resp or not resp.status_code == 200 or not data or not check_key(data, 'resultCode') or not data['resultCode'] == 'OK' or not check_key(data, 'resultObj') or not check_key(data['resultObj'], 'token') or not check_key(data['resultObj'], 'src') or not check_key(data['resultObj']['src'], 'sources') or not check_key(data['resultObj']['src']['sources'], 'src'):
            return playdata

        if check_key(data['resultObj']['src']['sources'], 'contentProtection') and check_key(data['resultObj']['src']['sources']['contentProtection'], 'widevine') and check_key(data['resultObj']['src']['sources']['contentProtection']['widevine'], 'licenseAcquisitionURL'):
            license = data['resultObj']['src']['sources']['contentProtection']['widevine']['licenseAcquisitionURL']

        path = data['resultObj']['src']['sources']['src']
        token = data['resultObj']['token']

        if not test:
            real_url = "{hostscheme}://{netloc}".format(hostscheme=urlparse(path).scheme, netloc=urlparse(path).netloc)
            proxy_url = "http://127.0.0.1:{proxy_port}".format(proxy_port=profile_settings['proxyserver_port'])

            path = path.replace(real_url, proxy_url)

            query = "UPDATE `vars` SET `stream_hostname`='{stream_hostname}' WHERE profile_id={profile_id}".format(stream_hostname=real_url, profile_id=1)
            query_settings(query=query, return_result=False, return_insert=False, commit=True)

        playdata = {'path': path, 'license': license, 'token': token, 'type': typestr, 'info': info}

        return playdata

    def vod_subscription(self):
        if not self.get_session():
            return None

        profile_settings = load_profile(profile_id=1)
        subscription = []

        series_url = '{api_url}/TRAY/SEARCH/VOD?from=1&to=9999&filter_contentType=GROUP_OF_BUNDLES,VOD&filter_contentSubtype=SERIES,VOD&filter_contentTypeExtended=VOD&filter_excludedGenres=erotiek&filter_technicalPackages=10078,10081,10258,10255&dfilter_packages=matchSubscription&orderBy=activationDate&sortOrder=desc'.format(api_url=profile_settings['api_url'])
        download = self.download(url=series_url, type='get', headers=None, data=None, json_data=False, return_json=True)
        data = download['data']
        resp = download['resp']

        if not resp or not resp.status_code == 200 or not data or not check_key(data, 'resultCode') or not data['resultCode'] == 'OK' or not check_key(data, 'resultObj') or not check_key(data['resultObj'], 'containers'):
            return False

        for row in data['resultObj']['containers']:
            subscription.append(row['metadata']['contentId'])

        write_file(file='vod_subscription.json', data=subscription, isJSON=True)

        return True

    def vod_seasons(self, id):
        profile_settings = load_profile(profile_id=1)
        seasons = []

        program_url = '{api_url}/CONTENT/DETAIL/GROUP_OF_BUNDLES/{id}'.format(api_url=profile_settings['api_url'], id=id)

        file = "cache" + os.sep + "vod_seasons_" + unicode(id) + ".json"

        if settings.getBool(key='enable_cache') and not is_file_older_than_x_minutes(file=ADDON_PROFILE + file, minutes=10):
            data = load_file(file=file, isJSON=True)
        else:
            if not self.get_session():
                return None

            download = self.download(url=program_url, type='get', headers=None, data=None, json_data=True, return_json=True)
            data = download['data']
            resp = download['resp']

            if resp and resp.status_code == 200 and data and check_key(data, 'resultCode') and data['resultCode'] == 'OK' and check_key(data, 'resultObj') and check_key(data['resultObj'], 'containers') and settings.getBool(key='enable_cache'):
                write_file(file=file, data=data, isJSON=True)

        if not data or not check_key(data['resultObj'], 'containers'):
            return None

        for row in data['resultObj']['containers']:
            for currow in row['containers']:
                if check_key(currow, 'metadata') and check_key(currow['metadata'], 'season') and currow['metadata']['contentSubtype'] == 'SEASON':
                    seasons.append({'id': currow['metadata']['contentId'], 'seriesNumber': currow['metadata']['season'], 'desc': currow['metadata']['shortDescription'], 'image': currow['metadata']['pictureUrl']})

        return seasons

    def vod_season(self, id):
        profile_settings = load_profile(profile_id=1)
        season = []
        episodes = []

        program_url = '{api_url}/CONTENT/DETAIL/BUNDLE/{id}'.format(api_url=profile_settings['api_url'], id=id)

        file = "cache" + os.sep + "vod_season_" + unicode(id) + ".json"

        if settings.getBool(key='enable_cache') and not is_file_older_than_x_minutes(file=ADDON_PROFILE + file, minutes=10):
            data = load_file(file=file, isJSON=True)
        else:
            if not self.get_session():
                return None

            download = self.download(url=program_url, type='get', headers=None, data=None, json_data=True, return_json=True)
            data = download['data']
            resp = download['resp']

            if resp and resp.status_code == 200 and data and check_key(data, 'resultCode') and data['resultCode'] == 'OK' and check_key(data, 'resultObj') and check_key(data['resultObj'], 'containers') and settings.getBool(key='enable_cache'):
                write_file(file=file, data=data, isJSON=True)

        if not data or not check_key(data['resultObj'], 'containers'):
            return None

        for row in data['resultObj']['containers']:
            for currow in row['containers']:
                if check_key(currow, 'metadata') and check_key(currow['metadata'], 'season') and currow['metadata']['contentSubtype'] == 'EPISODE' and not currow['metadata']['episodeNumber'] in episodes:
                    asset_id = ''

                    for asset in currow['assets']:
                        if check_key(asset, 'videoType') and asset['videoType'] == 'SD_DASH_PR' and check_key(asset, 'assetType') and asset['assetType'] == 'MASTER':
                            asset_id = asset['assetId']
                            break

                    episodes.append(currow['metadata']['episodeNumber'])
                    season.append({'id': currow['metadata']['contentId'], 'assetid': asset_id, 'duration': currow['metadata']['duration'], 'title': currow['metadata']['episodeTitle'], 'episodeNumber': '{season}.{episode}'.format(season=currow['metadata']['season'], episode=currow['metadata']['episodeNumber']), 'desc': currow['metadata']['shortDescription'], 'image': currow['metadata']['pictureUrl']})

        return season

    def download(self, url, type, headers=None, data=None, json_data=True, return_json=True, allow_redirects=True):
        if self._abortRequested or xbmc.Monitor().abortRequested():
            return { 'resp': None, 'data': None }

        session = Session(cookies_key='cookies')

        if headers:
            session.headers = headers

        if type == "post" and data:
            if json_data:
                resp = session.post(url, json=data, allow_redirects=allow_redirects)
            else:
                resp = session.post(url, data=data, allow_redirects=allow_redirects)
        else:
            resp = getattr(session, type)(url, allow_redirects=allow_redirects)

        if return_json:
            try:
                returned_data = json.loads(resp.json().decode('utf-8'))
            except:
                returned_data = resp.json()
        else:
            returned_data = resp

        return { 'resp': resp, 'data': returned_data }