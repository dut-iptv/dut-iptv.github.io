import os, re, requests, time, xbmc

from resources.lib.base import gui, settings
from resources.lib.base.constants import ADDON_ID, ADDON_PROFILE
from resources.lib.base.exceptions import Error
from resources.lib.base.log import log
from resources.lib.base.session import Session
from resources.lib.base.util import check_key, clean_filename, combine_playlist, download_files, find_highest_bandwidth, get_credentials, is_file_older_than_x_minutes, load_file, set_credentials, write_file
from resources.lib.language import _
from resources.lib.util import get_image, get_play_url, update_settings

try:
    from urllib.parse import urlparse, quote
except ImportError:
    from urllib import quote
    from urlparse import urlparse

try:
    unicode
except NameError:
    unicode = str

class APIError(Error):
    pass

class API(object):
    def new_session(self, force=False, retry=True, channels=False):
        self.check_vars()

        if self._debug_mode:
            log.debug('Executing: api.new_session')
            log.debug('Vars: force={force}, retry={retry}, channels={channels}'.format(force=force, retry=retry, channels=channels))
            log.debug('Access Token: {access_token}'.format(access_token=self._access_token))

        username = self._username
        password = self._password

        if len(self._access_token) > 0 and len(username) > 0 and not force and not channels and self._session_age > int(time.time() - 7200) and self._last_login_success:
            self.logged_in = True

            try:
                self._session
            except:
                user_agent = settings.get(key='_user_agent')

                HEADERS = {
                    'User-Agent':  user_agent,
                    'X-Client-Id': settings.get(key='_client_id') + "||" + user_agent,
                    'X-OESP-Token': self._access_token,
                    'X-OESP-Username': username,
                }

                if self._base_v3:
                    HEADERS['X-OESP-Profile-Id'] = settings.get(key='_profile_id')

                self._session = Session(headers=HEADERS)

                if self._debug_mode:
                    log.debug('Creating new Requests Session')
                    log.debug('Request Session Headers')
                    log.debug(self._session.headers)
                    log.debug('api.logged_in: {logged_in}'.format(logged_in=self.logged_in))
                    log.debug('Execution Done: api.new_session')

            return True

        self.logged_in = False

        if self._debug_mode:
            log.debug('api.logged_in: {logged_in}'.format(logged_in=self.logged_in))

        if not len(username) > 0:
            if self._debug_mode:
                log.debug('Username length = 0')
                log.debug('Execution Done: api.new_session')

            settings.setBool(key="_last_login_success", value=self.logged_in)
            self._last_login_success = self.logged_in

            return False

        if not len(password) > 0:
            if not force:
                if self._debug_mode:
                    log.debug('Password length = 0 and force is false')
                    log.debug('Execution Done: api.new_session')

                settings.setBool(key="_last_login_success", value=self.logged_in)
                self._last_login_success = self.logged_in

                return False

            password = gui.numeric(message=_.ASK_PASSWORD).strip()

            if not len(password) > 0:
                if self._debug_mode:
                    log.debug('Password length = 0')
                    log.debug('Execution Done: api.new_session')

                gui.ok(message=_.EMPTY_PASS, heading=_.LOGIN_ERROR_TITLE)
                settings.setBool(key="_last_login_success", value=self.logged_in)
                self._last_login_success = self.logged_in

                return False

        self.login(username=username, password=password, channels=channels, retry=retry)

        if self._debug_mode:
            log.debug('Execution Done: api.new_session')
            log.debug('api.logged_in: {logged_in}'.format(logged_in=self.logged_in))

        settings.setBool(key="_last_login_success", value=self.logged_in)
        self._last_login_success = self.logged_in

        if self.logged_in:
            return True

        return False

    def check_vars(self):
        try:
            self._debug_mode
        except:
            self._debug_mode = settings.getBool(key='enable_debug')

        if self._debug_mode:
            log.debug('Executing: api.check_vars')

        try:
            self._access_token
        except:
            self._access_token = settings.get(key='_access_token')

        try:
            self._base_v3
        except:
            self._base_v3 = settings.getBool(key='_base_v3')

        try:
            self._drm_token
        except:
            self._drm_token = settings.get(key='_drm_token')

        try:
            self._drm_locator
        except:
            self._drm_locator = settings.get(key='_drm_locator')

        try:
            self._drm_token_age
        except:
            self._drm_token_age = settings.getInt(key='_drm_token_age')

        try:
            self._tokenruntime
        except:
            self._tokenruntime = settings.getInt(key='_tokenruntime')

        try:
            self._tokenrun
        except:
            self._tokenrun = settings.getInt(key='_tokenrun')

        try:
            self._session_age
        except:
            self._session_age = settings.getInt(key='_session_age')

        try:
            self._last_login_success
        except:
            self._last_login_success = settings.getBool(key='_last_login_success')

        try:
            self._channels_age
        except:
            self._channels_age = settings.getInt(key='_channels_age')

        try:
            self._username
        except:
            try:
                creds
            except:
                creds = get_credentials()

            self._username = creds['username']

        try:
            self._abortRequested
        except:
            self._abortRequested = False

        try:
            self._password
        except:
            try:
                creds
            except:
                creds = get_credentials()

            self._password = creds['password']

        if self._debug_mode:
            log.debug('Execution Done: api.check_vars')

    def login(self, username, password, channels=False, retry=True):
        if self._debug_mode:
            log.debug('Executing: api.login')
            log.debug('Vars: username={username}, password={password}, channels={channels}, retry={retry}'.format(username=username, password=password, channels=channels, retry=retry))
            log.debug('Backoffice is V3: {backoffice}'.format(backoffice=self._base_v3))

        settings.remove(key='_access_token')
        self._access_token = ''
        user_agent = settings.get(key='_user_agent')

        HEADERS = {
            'User-Agent':  user_agent,
            'X-Client-Id': settings.get(key='_client_id') + "||" + user_agent,
        }

        self._session = Session(headers=HEADERS)

        if self._debug_mode:
            log.debug('Clear Setting _access_token')
            log.debug('Creating new Requests Session')
            log.debug('Request Session Headers')
            log.debug(self._session.headers)

        data = self.download(url=settings.get(key='_session_url'), type="post", code=None, data={"username": username, "password": password}, json_data=True, data_return=True, return_json=True, retry=retry, check_data=False)

        if data and check_key(data, 'reason') and data['reason'] == 'wrong backoffice':
            if self._debug_mode:
                log.debug('Wrong backoffice detected, switching')

            if not self._base_v3:
                settings.setBool(key='_base_v3', value=True)
                self._base_v3 = True
            else:
                settings.setBool(key='_base_v3', value=False)
                self._base_v3 = False

            update_settings()
            download_files()
            data = self.download(url=settings.get(key='_session_url'), type="post", code=None, data={"username": username, "password": password}, json_data=True, data_return=True, return_json=True, retry=retry, check_data=False)

        if self._debug_mode:
            log.debug('Backoffice is V3: {backoffice}'.format(backoffice=self._base_v3))

        if not data or not check_key(data, 'oespToken'):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.login')

            gui.ok(message=_.LOGIN_ERROR, heading=_.LOGIN_ERROR_TITLE)
            return False

        self._access_token = data['oespToken']
        settings.set(key='_access_token', value=self._access_token)

        self._session_age = time.time()
        settings.setInt(key='_session_age', value=self._session_age)

        if self._debug_mode:
            log.debug('Access Token: {access_token}'.format(access_token=self._access_token))

        if self._base_v3:
            settings.set(key='_profile_id', value=data['customer']['sharedProfileId'])
            self._session.headers.update({'X-OESP-Profile-Id': data['customer']['sharedProfileId']})
            settings.set(key='_household_id', value=data['customer']['householdId'])

            if self._debug_mode:
                log.debug('Profile ID: {profile_id}'.format(profile_id=data['customer']['sharedProfileId']))
                log.debug('Household ID: {household_id}'.format(household_id=data['customer']['householdId']))

        self._session.headers.update({'X-OESP-Token': self._access_token})
        self._session.headers.update({'X-OESP-Username': username})

        if self._debug_mode:
            log.debug('Settings _channels_age: {channels_age}'.format(channels_age=self._channels_age))
            log.debug('Time - 86400 seconds: {time}'.format(time=int(time.time() - 86400)))

        if channels or self._channels_age < int(time.time() - 86400):
            if not self.get_channels_for_user(location=data['locationId']):
                if self._debug_mode:
                    log.debug('Failure to retrieve channels')
                    log.debug('Execution Done: api.login')

                gui.ok(message=_.LOGIN_ERROR, heading=_.LOGIN_ERROR_TITLE)
                return False

            if self._base_v3:
                if username != self._username or len(unicode(settings.get(key='_watchlist_id'))) == 0:
                    self.get_watchlist_id()

        self._username = username
        self._password = password

        if settings.getBool(key='save_password', default=False):
            set_credentials(username=username, password=password)
        else:
            set_credentials(username=username, password='')

        self.logged_in = True

        if self._debug_mode:
            log.debug('Execution Done: api.login')

        return True

    def get_channels_for_user(self, location):
        if self._debug_mode:
            log.debug('Executing: api.get_channels_for_user')
            log.debug('Vars: location={location}'.format(location=location))

        channels_url = '{channelsurl}?byLocationId={location}&includeInvisible=true&personalised=true'.format(channelsurl=settings.get('_channels_url'), location=location)
        data = self.download(url=channels_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=False, check_data=False)

        if not data or not check_key(data, 'entryCount') or not check_key(data, 'channels'):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.get_channels_for_user')

            return False

        write_file(file="channels.json", data=data['channels'], isJSON=True)

        self.create_playlist()

        if self._debug_mode:
            log.debug('Execution Done: api.get_channels_for_user')

        return True

    def create_playlist(self):
        if self._debug_mode:
            log.debug('Executing: api.create_playlist')

        prefs = load_file(file="channel_prefs.json", isJSON=True)
        channels = load_file(file="channels.json", isJSON=True)

        playlist_all = u'#EXTM3U\n'
        playlist = u'#EXTM3U\n'

        for row in sorted(channels, key=lambda r: float(r.get('channelNumber', 'inf'))):
            channeldata = self.get_channel_data(row=row)
            id = unicode(channeldata['channel_id'])

            if len(id) > 0:
                path = 'plugin://{addonid}/?_=play_video&type=channel&id={channel}&_l=.pvr'.format(addonid=ADDON_ID, channel=channeldata['channel_id'])
                playlist_all += u'#EXTINF:-1 tvg-id="{id}" tvg-chno="{channel}" tvg-name="{name}" tvg-logo="{logo}" group-title="TV" radio="false",{name}\n{path}\n'.format(id=channeldata['channel_id'], channel=channeldata['channel_number'], name=channeldata['label'], logo=channeldata['station_image_large'], path=path)

                if not prefs or not check_key(prefs, id) or prefs[id]['epg'] == 'true':
                    playlist += u'#EXTINF:-1 tvg-id="{id}" tvg-chno="{channel}" tvg-name="{name}" tvg-logo="{logo}" group-title="TV" radio="false",{name}\n{path}\n'.format(id=channeldata['channel_id'], channel=channeldata['channel_number'], name=channeldata['label'], logo=channeldata['station_image_large'], path=path)

        self._channels_age = time.time()
        settings.setInt(key='_channels_age', value=self._channels_age)

        if self._debug_mode:
            log.debug('Setting _channels_age to: {channels_age}'.format(channels_age=self._channels_age))
            log.debug('Writing tv.m3u8: {playlist}'.format(playlist=playlist))

        write_file(file="tv.m3u8", data=playlist, isJSON=False)
        write_file(file="tv_all.m3u8", data=playlist_all, isJSON=False)
        combine_playlist()

        if self._debug_mode:
            log.debug('Execution Done: api.create_playlist')

    def get_watchlist_id(self):
        if self._debug_mode:
            log.debug('Executing: api.get_watchlist_id')

        watchlist_url = 'https://prod.spark.ziggogo.tv/nld/web/watchlist-service/v1/watchlists/profile/{profile_id}?language=nl&maxResults=1&order=DESC&sharedProfile=true&sort=added'.format(profile_id=settings.get(key='_profile_id'))

        data = self.download(url=watchlist_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=False, check_data=False)

        if not data or not check_key(data, 'watchlistId'):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.get_watchlist_id')

            return False

        settings.set(key='_watchlist_id', value=data['watchlistId'])

        if self._debug_mode:
            log.debug('Watchlist ID: {watchlist_id}'.format(watchlist_id=data['watchlistId']))
            log.debug('Execution Done: api.get_watchlist_id')

        return True

    def test_channels(self, tested=False, channel=None):
        if self._debug_mode:
            log.debug('Executing: api.test_channels')
            log.debug('Vars: tested={tested}, channel={channel}'.format(tested=tested, channel=channel))

        if channel:
            channel = unicode(channel)

        try:
            if not self._last_login_success or not settings.getBool(key='run_tests'):
                return 5

            settings.setBool(key='_test_running', value=True)
            channels = load_file(file="channels.json", isJSON=True)
            results = load_file(file="channel_test.json", isJSON=True)

            count = 0
            first = True
            last_tested_found = False
            test_run = False
            user_agent = settings.get(key='_user_agent')
            listing_url = settings.get(key='_listings_url')

            if not results:
                results = {}

            for row in channels:
                if count == 5 or (count == 1 and tested):
                    if test_run:
                        self.update_prefs()

                    settings.setBool(key='_test_running', value=False)
                    return count

                channeldata = self.get_channel_data(row=row)
                id = unicode(channeldata['channel_id'])

                if len(id) > 0:
                    if channel:
                        if not id == channel:
                            continue
                    elif tested and check_key(results, 'last_tested'):
                        if unicode(results['last_tested']) == id:
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
                    live = 'false'
                    replay = 'false'
                    epg = 'false'
                    guide = 'false'

                    if settings.getInt(key='_last_playing') > int(time.time() - 300):
                        if test_run:
                            self.update_prefs()

                        settings.setBool(key='_test_running', value=False)
                        return 5

                    playdata = self.play_url(type='channel', id=channeldata['channel_id'], test=True)

                    if first and not self._last_login_success:
                        if test_run:
                            self.update_prefs()

                        settings.setBool(key='_test_running', value=False)
                        return 5

                    if len(playdata['path']) > 0:
                        CDMHEADERS = {
                            'User-Agent': user_agent,
                            'X-Client-Id': settings.get(key='_client_id') + '||' + user_agent,
                            'X-OESP-Token': self._access_token,
                            'X-OESP-Username': self._username,
                            'X-OESP-License-Token': self._drm_token,
                            'X-OESP-DRM-SchemeIdUri': 'urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
                            'X-OESP-Content-Locator': playdata['locator'],
                        }

                        self._session2 = Session(headers=CDMHEADERS)
                        resp = self._session2.get(playdata['path'])

                        if resp.status_code == 200:
                            livebandwidth = find_highest_bandwidth(xml=resp.text)
                            live = 'true'

                    if check_key(results, id) and first and not tested:
                        first = False

                        if live == 'true':
                            continue
                        else:
                            if test_run:
                                self.update_prefs()

                            settings.setBool(key='_test_running', value=False)
                            return 5

                    first = False
                    counter = 0

                    while not self._abortRequested and not xbmc.Monitor().abortRequested() and counter < 65:
                        if self._abortRequested or xbmc.Monitor().waitForAbort(1):
                            self._abortRequested = True
                            break

                        counter += 1

                        if settings.getInt(key='_last_playing') > int(time.time() - 300):
                            if test_run:
                                self.update_prefs()

                            settings.setBool(key='_test_running', value=False)
                            return 5

                    if self._abortRequested or xbmc.Monitor().abortRequested():
                        return 5

                    listing_url = '{listings_url}?byEndTime={time}~&byStationId={channel}&range=1-1&sort=startTime'.format(listings_url=listing_url, time=int(int(time.time() - 86400) * 1000), channel=id)
                    data = self.download(url=listing_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)
                    program_id = None

                    if data and check_key(data, 'listings'):
                        for row in data['listings']:
                            program_id = row['id']

                    if program_id:
                        if settings.getInt(key='_last_playing') > int(time.time() - 300):
                            if test_run:
                                self.update_prefs()

                            settings.setBool(key='_test_running', value=False)
                            return 5

                        playdata = self.play_url(type='program', id=program_id, test=True)

                        if len(playdata['path']) > 0:
                            CDMHEADERS = {
                                'User-Agent': user_agent,
                                'X-Client-Id': settings.get(key='_client_id') + '||' + user_agent,
                                'X-OESP-Token': self._access_token,
                                'X-OESP-Username': self._username,
                                'X-OESP-License-Token': self._drm_token,
                                'X-OESP-DRM-SchemeIdUri': 'urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
                                'X-OESP-Content-Locator': playdata['locator'],
                            }

                            self._session2 = Session(headers=CDMHEADERS)
                            resp = self._session2.get(playdata['path'])

                            if resp.status_code == 200:
                                replaybandwidth = find_highest_bandwidth(xml=resp.text)
                                replay = 'true'

                    if os.path.isfile(ADDON_PROFILE + id + '_replay.json'):
                        guide = 'true'

                        if live == 'true':
                            epg = 'true'

                    results[id] = {
                        'id': id,
                        'live': live,
                        'replay': replay,
                        'livebandwidth': livebandwidth,
                        'replaybandwidth': replaybandwidth,
                        'epg': epg,
                        'guide': guide,
                    }

                    results['last_tested'] = id

                    if not self._abortRequested:
                        write_file(file="channel_test.json", data=results, isJSON=True)

                    test_run = True
                    counter = 0

                    while not self._abortRequested and not xbmc.Monitor().abortRequested() and counter < 15:
                        if self._abortRequested or xbmc.Monitor().waitForAbort(1):
                            self._abortRequested = True
                            break

                        counter += 1

                        if settings.getInt(key='_last_playing') > int(time.time() - 300):
                            if test_run:
                                self.update_prefs()

                            settings.setBool(key='_test_running', value=False)
                            return 5

                    if self._abortRequested or xbmc.Monitor().abortRequested():
                        return 5

                    count += 1
        except:
            if test_run:
                self.update_prefs()

            count = 5

        settings.setBool(key='_test_running', value=False)

        if self._debug_mode:
            log.debug('Execution Done: api.test_channels')

        return count

    def update_prefs(self):
        if self._debug_mode:
            log.debug('Executing: api.update_prefs')

        prefs = load_file(file="channel_prefs.json", isJSON=True)
        results = load_file(file="channel_test.json", isJSON=True)
        channels = load_file(file="channels.json", isJSON=True)

        if not results:
            results = {}

        if not prefs:
            prefs = {}

        if not channels:
            channels = {}

        for row in channels:
            channeldata = self.get_channel_data(row=row)
            id = unicode(channeldata['channel_id'])

            if len(unicode(id)) == 0:
                continue

            keys = ['live', 'replay', 'epg']

            for key in keys:
                if not check_key(prefs, id) or not check_key(prefs[id], key):
                    if not check_key(results, id):
                        if not check_key(prefs, id):
                            prefs[id] = {
                                key: 'true',
                                key + '_choice': 'auto'
                            }
                        else:
                            prefs[id][key] = 'true'
                            prefs[id][key + '_choice'] = 'auto'
                    else:
                        result_value = results[id][key]

                        if not check_key(prefs, id):
                            prefs[id] = {
                                key: result_value,
                                key + '_choice': 'auto'
                            }
                        else:
                            prefs[id][key] = result_value
                            prefs[id][key + '_choice'] = 'auto'
                elif prefs[id][key + '_choice'] == 'auto' and check_key(results, id):
                    prefs[id][key] = results[id][key]

        write_file(file="channel_prefs.json", data=prefs, isJSON=True)

        if self._debug_mode:
            log.debug('Execution Done: api.update_prefs')

    def get_channel_data(self, row):
        if self._debug_mode:
            log.debug('Executing: api.get_channel_data')
            log.debug('Vars: row={row}'.format(row=row))

        channeldata = {
            'channel_id': '',
            'channel_number': '',
            'description': '',
            'label': '',
            'station_image_large': '',
            'stream': ''
        }

        if check_key(row, 'stationSchedules') and check_key(row, 'channelNumber') and check_key(row['stationSchedules'][0], 'station') and check_key(row['stationSchedules'][0]['station'], 'id') and check_key(row['stationSchedules'][0]['station'], 'title') and check_key(row['stationSchedules'][0]['station'], 'videoStreams'):
            path = ADDON_PROFILE + "images" + os.sep + unicode(row['stationSchedules'][0]['station']['id']) + ".png"

            desc = ''
            image = ''

            if os.path.isfile(path):
                image = path
            else:
                if check_key(row['stationSchedules'][0]['station'], 'images'):
                    image = get_image("station-logo", row['stationSchedules'][0]['station']['images'])

            if check_key(row['stationSchedules'][0]['station'], 'description'):
                desc = row['stationSchedules'][0]['station']['description']

            channeldata = {
                'channel_id': row['stationSchedules'][0]['station']['id'],
                'channel_number': row['channelNumber'],
                'description': desc,
                'label': row['stationSchedules'][0]['station']['title'],
                'station_image_large': image,
                'stream': row['stationSchedules'][0]['station']['videoStreams']
            }

        if self._debug_mode:
            log.debug('Returned data: {channeldata}'.format(channeldata=channeldata))
            log.debug('Execution Done: api.get_channel_data')

        return channeldata

    def play_url(self, type, id=None, test=False, from_beginning='False'):
        if self._debug_mode:
            log.debug('Executing: api.play_url')
            log.debug('Vars: type={type}, id={id}, test={test}'.format(type=type, id=id, test=test))

        playdata = {'path': '', 'license': '', 'token': '', 'locator': '', 'type': ''}

        info = {}
        base_listing_url = settings.get(key='_listings_url')
        urldata = None
        urldata2 = None
        path = None
        locator = None

        if not type or not len(unicode(type)) > 0 or not id or not len(unicode(id)) > 0:
            if self._debug_mode:
                log.debug('Failure executing api.play_url, no id or type set')
                log.debug('Execution Done: api.play_url')

            return playdata

        if not test:
            while not self._abortRequested and not xbmc.Monitor().abortRequested() and settings.getBool(key='_test_running'):
                settings.setInt(key='_last_playing', value=time.time())

                if self._abortRequested or xbmc.Monitor().waitForAbort(1):
                    self._abortRequested = True
                    break

            if self._abortRequested or xbmc.Monitor().abortRequested():
                return 5

        if type == 'channel':
            rows = load_file(file='channels.json', isJSON=True)

            if self._debug_mode:
                log.debug('Channels')
                log.debug(rows)

            if rows:
                for row in rows:
                    channeldata = self.get_channel_data(row=row)

                    if channeldata['channel_id'] == id:
                        urldata = get_play_url(content=channeldata['stream'])

                        if self._debug_mode:
                            log.debug('Found channel, stream={stream}, urldata={url}'.format(stream=channeldata['stream'], url=urldata))

                        break

            listing_url = '{listings_url}?byEndTime={time}~&byStationId={channel}&range=1-1&sort=startTime'.format(listings_url=base_listing_url, time=int(time.time() * 1000), channel=id)
            data = self.download(url=listing_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

            if data and check_key(data, 'listings'):
                for row in data['listings']:
                    if check_key(row, 'program'):
                        info = row['program']
        elif type == 'program':
            listings_url = "{listings_url}/{id}".format(listings_url=base_listing_url, id=id)
            data = self.download(url=listings_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

            if not data or not check_key(data, 'program'):
                if self._debug_mode:
                    log.debug('Failure to retrieve expected data')
                    log.debug('Execution Done: api.play_url')

                return playdata

            info = data['program']
        elif type == 'vod':
            mediaitems_url = '{mediaitems_url}/{id}'.format(mediaitems_url=settings.get(key='_mediaitems_url'), id=id)

            data = self.download(url=mediaitems_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

            if not data:
                if self._debug_mode:
                    log.debug('Failure to retrieve expected data')
                    log.debug('Execution Done: api.play_url')

                return playdata

            info = data

        if check_key(info, 'videoStreams'):
            urldata2 = get_play_url(content=info['videoStreams'])

            if self._debug_mode:
                log.debug('Found stream in info, urldata2={url}'.format(url=urldata2))

        if not type == 'channel' and (not urldata2 or not check_key(urldata2, 'play_url') or not check_key(urldata2, 'locator') or urldata2['play_url'] == 'http://Playout/using/Session/Service') and self._base_v3:
            urldata2 = {}

            if type == 'program':
                playout_str = 'replay'
            elif type == 'vod':
                playout_str = 'vod'
            else:
                if self._debug_mode:
                    log.debug('Failure, unknown type={type}'.format(type=type))
                    log.debug('Execution Done: api.play_url')

                return playdata

            playout_url = '{base_url}/playout/{playout_str}/{id}?abrType=BR-AVC-DASH'.format(base_url=settings.get(key='_base_url'), playout_str=playout_str, id=id)
            data = self.download(url=playout_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

            if not data or not check_key(data, 'url') or not check_key(data, 'contentLocator'):
                return playdata

            urldata2['play_url'] = data['url']
            urldata2['locator'] = data['contentLocator']

            if self._debug_mode:
                log.debug('Found stream using playout, urldata2={url}'.format(url=urldata2))

        if urldata and urldata2 and check_key(urldata, 'play_url') and check_key(urldata, 'locator') and check_key(urldata2, 'play_url') and check_key(urldata2, 'locator'):
            path = urldata['play_url']
            locator = urldata['locator']

            if not from_beginning == 'False':
                path = urldata2['play_url']
                locator = urldata2['locator']
                type = 'program'
            elif settings.getBool(key='ask_start_from_beginning'):
                if self._debug_mode:
                    log.debug('Offering choice between live and start from beginning')

                if gui.yes_no(message=_.START_FROM_BEGINNING, heading=info['title']):
                    path = urldata2['play_url']
                    locator = urldata2['locator']
                    type = 'program'
        else:
            if urldata and check_key(urldata, 'play_url') and check_key(urldata, 'locator'):
                path = urldata['play_url']
                locator = urldata['locator']
            elif urldata2 and check_key(urldata2, 'play_url') and check_key(urldata2, 'locator'):
                path = urldata2['play_url']
                locator = urldata2['locator']
                type = 'program'

        if self._debug_mode:
            log.debug('path={path}, locator={locator}, type={type}'.format(path=path, locator=locator, type=type))

        if not locator or not len(unicode(locator)) > 0:
            if self._debug_mode:
                log.debug('Failure, empty locator')
                log.debug('Execution Done: api.play_url')

            return playdata

        license = settings.get('_widevine_url')

        if self._abortRequested or xbmc.Monitor().abortRequested():
            return playdata

        token = self.get_play_token(locator=locator, path=path, force=True)

        if not token or not len(unicode(token)) > 0:
            if self._debug_mode:
                log.debug('Failure, empty token')
                log.debug('Execution Done: api.play_url')

            gui.ok(message=_.NO_STREAM_AUTH, heading=_.PLAY_ERROR)
            return playdata

        if not test:
            token = 'WIDEVINETOKEN'

        token_regex = re.search(r"(?<=;vxttoken=)(.*?)(?=/)", path)

        if token_regex and token_regex.group(1) and len(token_regex.group(1)) > 0:
            path = path.replace(token_regex.group(1), token)
        else:
            if 'sdash/' in path:
                spliturl = path.split('sdash/', 1)

                if len(spliturl) == 2:
                    if self._base_v3:
                        path = '{urlpart1}sdash;vxttoken={token}/{urlpart2}'.format(urlpart1=spliturl[0], token=token, urlpart2=spliturl[1])
                    else:
                        path = '{urlpart1}sdash;vxttoken={token}/{urlpart2}?device=Orion-Replay-DASH'.format(urlpart1=spliturl[0], token=token, urlpart2=spliturl[1])
            else:
                spliturl = path.rsplit('/', 1)

                if len(spliturl) == 2:
                    path = '{urlpart1};vxttoken={token}/{urlpart2}'.format(urlpart1=spliturl[0], token=token, urlpart2=spliturl[1])

        if not test:
            real_url = "{hostscheme}://{netloc}".format(hostscheme=urlparse(path).scheme, netloc=urlparse(path).netloc)
            proxy_url = "http://127.0.0.1:{proxy_port}".format(proxy_port=settings.getInt(key='_proxyserver_port'))

            if self._debug_mode:
                log.debug('Real url: {real_url}'.format(real_url=real_url))
                log.debug('Proxy url: {proxy_url}'.format(proxy_url=proxy_url))

            settings.set(key='_stream_hostname', value=real_url)
            path = path.replace(real_url, proxy_url)

        playdata = {'path': path, 'license': license, 'token': token, 'locator': locator, 'info': info, 'type': type}

        if self._debug_mode:
            log.debug('Returned Playdata: {playdata}'.format(playdata=playdata))
            log.debug('Execution Done: api.play_url')

        return playdata

    def get_play_token(self, locator=None, path=None, force=False):
        if self._debug_mode:
            log.debug('Executing: api.get_play_token')
            log.debug('Vars: locator={locator}, path={path}, force={force}'.format(locator=locator, path=path, force=force))
            log.debug('Settings _drm_token_age: {token_age}'.format(token_age=self._drm_token_age))
            log.debug('Time - 50 seconds: {time}'.format(time=int(time.time() - 50)))
            log.debug('Settings _tokenrun: {tokenrun}'.format(tokenrun=self._tokenrun))
            log.debug('Settings _tokenruntime: {tokenruntime}'.format(tokenruntime=self._tokenruntime))
            log.debug('Time - 30 seconds: {time}'.format(time=int(time.time() - 30)))

        if self._drm_token_age < int(time.time() - 50) and (self._tokenrun == 0 or self._tokenruntime < int(time.time() - 30)):
            force = True

        if self._debug_mode:
            log.debug('Force: {force}'.format(force=force))
            log.debug('Settings _drm_locator: {drm_locator}'.format(drm_locator=self._drm_locator))
            log.debug('Settings _drm_token_age: {drm_token_age}'.format(drm_token_age=self._drm_token_age))
            log.debug('Time - 90 seconds: {time}'.format(time=int(time.time() - 90)))

        if locator != self._drm_locator or self._drm_token_age < int(time.time() - 90) or force:
            self._tokenrun = 1
            settings.setInt(key='_tokenrun', value=1)
            self._tokenruntime = time.time()
            settings.setInt(key='_tokenruntime', value=self._tokenruntime)

            if self._debug_mode:
                log.debug('Setting _tokenrun to: {tokenrun}'.format(tokenrun=self._tokenrun))
                log.debug('Setting _tokenruntime to: {tokenruntime}'.format(tokenruntime=self._tokenruntime))

            if self._base_v3 and 'sdash' in path:
                jsondata = {"contentLocator": locator, "drmScheme": "sdash:BR-AVC-DASH"}
            else:
                jsondata = {"contentLocator": locator}

            data = self.download(url=settings.get(key='_token_url'), type="post", code=[200], data=jsondata, json_data=True, data_return=True, return_json=True, retry=True, check_data=False)

            self._tokenrun = 0
            settings.setInt(key="_tokenrun", value=0)

            if not data or not check_key(data, 'token'):
                if self._debug_mode:
                    log.debug('Failure to retrieve expected data')
                    log.debug('Execution Done: api.get_play_token')

                return None

            self._drm_token = data['token']
            settings.set(key='_drm_token', value=self._drm_token)
            self._drm_token_age = time.time()
            settings.setInt(key='_drm_token_age', value=self._drm_token_age)
            self._drm_locator = locator
            settings.set(key='_drm_locator', value=self._drm_locator)

            if self._debug_mode:
                log.debug('Setting _drm_token to: {token}'.format(token=self._drm_token))
                log.debug('Setting _drm_token_age to: {drm_token_age}'.format(drm_token_age=self._drm_token_age))
                log.debug('Setting _drm_locator to: {drm_locator}'.format(drm_locator=self._drm_locator))

        if self._debug_mode:
            log.debug('Returned Token: {token}'.format(token=self._drm_token))
            log.debug('Execution Done: api.get_play_token')

        return self._drm_token

    def add_to_watchlist(self, id, type):
        if self._debug_mode:
            log.debug('Executing: api.add_to_watchlist')
            log.debug('Vars: id={id}, type={type}'.format(id=id, type=type))

        if type == "item":
            mediaitems_url = '{listings_url}/{id}'.format(listings_url=settings.get(key='_listings_url'), id=id)
            data = self.download(url=mediaitems_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

            if not data or not check_key(data, 'mediaGroupId'):
                if self._debug_mode:
                    log.debug('Failure to retrieve expected data')
                    log.debug('Execution Done: api.list_watchlist')

                return False

            id = data['mediaGroupId']

        if self._debug_mode:
            log.debug('Vars: id={id}, type={type}'.format(id=id, type=type))

        if self._base_v3:
            watchlist_url = 'https://prod.spark.ziggogo.tv/nld/web/watchlist-service/v1/watchlists/{watchlist_id}/entries/{id}?sharedProfile=true'.format(watchlist_id=settings.get(key='_watchlist_id'), id=id)
        else:
            watchlist_url = '{watchlist_url}/entries'.format(watchlist_url=settings.get(key='_watchlist_url'))

        data = self.download(url=watchlist_url, type="post", code=[204], data={"mediaGroup": {'id': id}}, json_data=True, data_return=False, return_json=False, retry=True, check_data=False)

        if self._debug_mode:
            log.debug('Execution Done: api.add_to_watchlist')

        return data

    def list_watchlist(self):
        if self._debug_mode:
            log.debug('Executing: api.list_watchlist')

        if self._base_v3:
            watchlist_url = 'https://prod.spark.ziggogo.tv/nld/web/watchlist-service/v1/watchlists/profile/{profile_id}?language=nl&order=DESC&sharedProfile=true&sort=added'.format(profile_id=settings.get(key='_profile_id'))
        else:
            watchlist_url = settings.get(key='_watchlist_url')

        data = self.download(url=watchlist_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

        if not data or not check_key(data, 'entries'):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.list_watchlist')

            return False

        if self._debug_mode:
            log.debug('Execution Done: api.list_watchlist')

        return data

    def remove_from_watchlist(self, id):
        if self._debug_mode:
            log.debug('Executing: api.remove_from_watchlist')
            log.debug('Vars: id={id}'.format(id=id))

        if self._base_v3:
            remove_url = 'https://prod.spark.ziggogo.tv/nld/web/watchlist-service/v1/watchlists/{watchlist_id}/entries/{id}?sharedProfile=true'.format(watchlist_id=settings.get(key='_watchlist_id'), id=id)
        else:
            remove_url = '{watchlist_url}/entries/{id}'.format(watchlist_url=settings.get(key='_watchlist_url'), id=id)

        resp = self.download(url=remove_url, type="delete", code=[204], data=None, json_data=False, data_return=False, return_json=False, retry=True, check_data=False)

        if self._debug_mode:
            log.debug('Remove from watchlist result: {resp}'.format(resp=resp))

        log.debug('Execution Done: api.remove_from_watchlist')

        return resp

    def watchlist_listing(self, id):
        if self._debug_mode:
            log.debug('Executing: api.watchlist_listing')
            log.debug('Vars: id={id}'.format(id=id))

        end = int(time.time() * 1000)
        start = end - (7 * 24 * 60 * 60 * 1000)

        mediaitems_url = '{media_items_url}?&byMediaGroupId={id}&byStartTime={start}~{end}&range=1-250&sort=startTime%7Cdesc'.format(media_items_url=settings.get(key='_listings_url'), id=id, start=start, end=end)
        data = self.download(url=mediaitems_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

        if not data or not check_key(data, 'listings'):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.watchlist_listing')

            return False

        if self._debug_mode:
            log.debug('Execution Done: api.watchlist_listing')

        return data

    def online_search(self, search):
        if self._debug_mode:
            log.debug('Executing: api.online_search')
            log.debug('Vars: search={search}'.format(search=search))

        if self._base_v3:
            if self._debug_mode:
                log.debug('Online search is disabled in V3')

            return False

        end = int(time.time() * 1000)
        start = end - (7 * 24 * 60 * 60 * 1000)
        enable_cache = settings.getBool(key='enable_cache')

        vodstr = ''

        file = "cache" + os.sep + "search_" + clean_filename(search) + ".json"

        search_url = '{search_url}?byBroadcastStartTimeRange={start}~{end}&numItems=25&byEntitled=true&personalised=true&q={search}'.format(search_url=settings.get(key='_search_url'), start=start, end=end, search=quote(search))

        if enable_cache and not is_file_older_than_x_minutes(file=ADDON_PROFILE + file, minutes=10):
            if self._debug_mode:
                log.debug('Loading JSON data from cache, file={file}'.format(file=file))

            data = load_file(file=file, isJSON=True)
        else:
            data = self.download(url=search_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

            if data and (check_key(data, 'tvPrograms') or check_key(data, 'moviesAndSeries')) and enable_cache:
                if self._debug_mode:
                    log.debug('Writing JSON data to cache, file={file}'.format(file=file))

                write_file(file=file, data=data, isJSON=True)

        if not data or (not check_key(data, 'tvPrograms') and not check_key(data, 'moviesAndSeries')):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.online_search')

            return False

        if self._debug_mode:
            log.debug('Execution Done: api.online_search')

        return data

    def check_data(self, resp, json=False):
        if self._debug_mode:
            log.debug('Executing: api.check_data')
            log.debug('Vars: resp={resp}, json={json}'.format(resp='Unaltered response, see above', json=json))

        if self._debug_mode:
            log.debug('Execution Done: api.check_data')

        return True

    def download(self, url, type, code=None, data=None, json_data=True, data_return=True, return_json=True, retry=True, check_data=True, allow_redirects=True):
        if self._abortRequested or xbmc.Monitor().abortRequested():
            return None

        if self._debug_mode:
            log.debug('Executing: api.download')
            log.debug('Vars: url={url}, type={type}, code={code}, data={data}, json_data={json_data}, data_return={data_return}, return_json={return_json}, retry={retry}, check_data={check_data}, allow_redirects={allow_redirects}'.format(url=url, type=type, code=code, data=data, json_data=json_data, data_return=data_return, return_json=return_json, retry=retry, check_data=check_data, allow_redirects=allow_redirects))

        if type == "post" and data:
            if json_data:
                resp = self._session.post(url, json=data, allow_redirects=allow_redirects)
            else:
                resp = self._session.post(url, data=data, allow_redirects=allow_redirects)
        else:
            resp = getattr(self._session, type)(url, allow_redirects=allow_redirects)

        if self._debug_mode:
            log.debug('Response')
            log.debug(resp.text)
            log.debug('Response status code: {status_code}'.format(status_code=resp.status_code))

        if (code and not resp.status_code in code) or (check_data and not self.check_data(resp=resp)):
            if not retry:
                if self._debug_mode:
                    log.debug('Not retrying')
                    log.debug('Returned data: None')
                    log.debug('Execution Done: api.download')

                return None

            if self._debug_mode:
                log.debug('Trying to update login data')

            self.new_session(force=True, retry=False)

            if not self.logged_in:
                if self._debug_mode:
                    log.debug('Not logged in at retry')
                    log.debug('Returned data: None')
                    log.debug('Execution Done: api.download')

                return None

            if type == "post" and data:
                if json_data:
                    resp = self._session.post(url, json=data, allow_redirects=allow_redirects)
                else:
                    resp = self._session.post(url, data=data, allow_redirects=allow_redirects)
            else:
                resp = getattr(self._session, type)(url, allow_redirects=allow_redirects)

            if self._debug_mode:
                log.debug('Response')
                log.debug(resp.text)
                log.debug('Response status code: {status_code}'.format(status_code=resp.status_code))

            if (code and not resp.status_code in code) or (check_data and not self.check_data(resp=resp)):
                if self._debug_mode:
                    log.debug('Failure on retry')
                    log.debug('Returned data: None')
                    log.debug('Execution Done: api.download')

                return None

        if data_return:
            try:
                if return_json:
                    try:
                        returned_data = json.loads(resp.json().decode('utf-8'))
                    except:
                        returned_data = resp.json()

                    if self._debug_mode:
                        log.debug('Returned data: {data}'.format(data=returned_data))
                        log.debug('Execution Done: api.download')

                    return returned_data
                else:
                    if self._debug_mode:
                        log.debug('Returned data: Unaltered response, see above')
                        log.debug('Execution Done: api.download')

                    return resp
            except:
                pass

        if self._debug_mode:
            log.debug('Returned data: True')
            log.debug('Execution Done: api.download')

        return True