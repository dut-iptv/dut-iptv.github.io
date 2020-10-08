import json, os, re, time, xbmc

from resources.lib.base import gui, settings
from resources.lib.base.constants import ADDON_ID, ADDON_PROFILE
from resources.lib.base.exceptions import Error
from resources.lib.base.log import log
from resources.lib.base.session import Session
from resources.lib.base.util import check_key, clean_filename, combine_playlist, find_highest_bandwidth, get_credentials, is_file_older_than_x_minutes, load_file, set_credentials, write_file
from resources.lib.constants import CONST_BASE_URL
from resources.lib.language import _

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

try:
    unicode
except NameError:
    unicode = str

class APIError(Error):
    pass

class API(object):
    def new_session(self, force=False, retry=False, channels=False):
        self.check_vars()

        if self._debug_mode:
            log.debug('Executing: api.new_session')
            log.debug('Vars: force={force}, retry={retry}, channels={channels}'.format(force=force, retry=retry, channels=channels))
            log.debug('Cookies: {cookies}'.format(cookies=self._cookies))

        username = self._username
        password = self._password

        if len(self._cookies) > 0 and len(username) > 0 and not force and not channels and self._session_age > int(time.time() - 7200) and self._last_login_success:
            self.logged_in = True

            try:
                self._session
            except:
                self._session = Session(cookies_key='_cookies')
                self._session.headers.update({'X_CSRFToken': self._csrf_token})

                if self._debug_mode:
                    log.debug('Creating new Requests Session')
                    log.debug('Request Session Headers')
                    log.debug(self._session.headers)
                    log.debug('api.logged_in: {logged_in}'.format(logged_in=self.logged_in))

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
            self._cookies
        except:
            self._cookies = settings.get(key='_cookies')

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
            self._enable_cache
        except:
            self._enable_cache = settings.getBool(key='enable_cache')

        try:
            self._devicekey
        except:
            self._devicekey = settings.get(key='_devicekey')

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

        try:
            self._csrf_token
        except:
            self._csrf_token = settings.get(key='_csrf_token')

        if self._debug_mode:
            log.debug('Execution Done: api.check_vars')

    def login(self, username, password, channels=False, retry=False):
        if self._debug_mode:
            log.debug('Executing: api.login')
            log.debug('Vars: username={username}, password={password}, channels={channels}, retry={retry}'.format(username=username, password=password, channels=channels, retry=retry))

        settings.remove(key='_cookies')
        self._cookies = ''
        settings.remove(key='_csrf_token')
        self._csrf_token = ''
        self._session = Session(cookies_key='_cookies')

        if self._debug_mode:
            log.debug('Clear Setting _cookies')
            log.debug('Creating new Requests Session')
            log.debug('Request Session Headers')
            log.debug(self._session.headers)

        deviceID = self._devicekey

        login_url = '{base_url}/VSP/V3/Authenticate?from=throughMSAAccess'.format(base_url=CONST_BASE_URL)

        session_post_data = {
            "authenticateBasic": {
                'clientPasswd': password,
                'isSupportWebpImgFormat': '0',
                'lang': 'nl',
                'needPosterTypes': [
                    '1',
                    '2',
                    '3',
                    '4',
                    '5',
                    '6',
                    '7',
                ],
                'timeZone': 'Europe/Amsterdam',
                'userID': username,
                'userType': '0',
            },
            'authenticateDevice': {
                'CADeviceInfos': [
                    {
                        'CADeviceID': deviceID,
                        'CADeviceType': '7',
                    },
                ],
                'deviceModel': '3103_PCClient',
                'physicalDeviceID': deviceID,
                'terminalID': deviceID,
            },
            'authenticateTolerant': {
                'areaCode': '',
                'bossID': '',
                'subnetID': '',
                'templateName': '',
                'userGroup': '',
            },
        }

        self._session.headers.update({'Content-Type': 'application/json'})

        data = self.download(url=login_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=retry, check_data=True)

        if not data or not check_key(data, 'csrfToken'):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.login')

            gui.ok(message=_.LOGIN_ERROR, heading=_.LOGIN_ERROR_TITLE)
            self.clear_session()
            return False

        self._csrf_token = data['csrfToken']
        settings.set(key='_csrf_token', value=self._csrf_token)
        self._session.headers.update({'X_CSRFToken': self._csrf_token})
        user_filter = data['userFilter']
        self._session_age = time.time()
        settings.setInt(key='_session_age', value=self._session_age)

        if self._debug_mode:
            log.debug('CSRF Token: {session_token}'.format(session_token=self._csrf_token))
            log.debug('Settings _channels_age: {channels_age}'.format(channels_age=self._channels_age))
            log.debug('Time - 86400 seconds: {time}'.format(time=int(time.time() - 86400)))

        if channels or self._channels_age < int(time.time() - 86400):
            channel_url = '{base_url}/VSP/V3/QueryChannelListBySubject?from=throughMSAAccess'.format(base_url=CONST_BASE_URL)
            session_post_data = {
                'contentTypes': [],
                'count': '1000',
                'filter': {
                    'subscriptionTypes': [
                        '0',
                        '1',
                    ]
                },
                'isReturnAllMedia': '0',
                'offset': '0',
                'subjectID': '-1',
            }

            data = self.download(url=channel_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=False, check_data=True)

            if not data or not check_key(data, 'total'):
                if self._debug_mode:
                    log.debug('Failure to retrieve expected data')
                    log.debug('Execution Done: api.login')

                gui.ok(message=_.LOGIN_ERROR, heading=_.LOGIN_ERROR_TITLE)
                self.clear_session()
                return False

            channel_all_url = '{base_url}/VSP/V3/QueryAllChannel?userFilter={user_filter}&from=inMSAAccess'.format(base_url=CONST_BASE_URL, user_filter=user_filter)
            session_post_data = {
                'isReturnAllMedia': '0'
            }

            data2 = self.download(url=channel_all_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=False, check_data=True)

            if not data2 or not check_key(data2, 'total'):
                if self._debug_mode:
                    log.debug('Failure to retrieve expected data')
                    log.debug('Execution Done: api.login')

                gui.ok(message=_.LOGIN_ERROR, heading=_.LOGIN_ERROR_TITLE)
                self.clear_session()
                return False

            channel_no_url = '{base_url}/VSP/V3/QueryAllChannelDynamicProperties?from=inMSAAccess'.format(base_url=CONST_BASE_URL)

            data3 = self.download(url=channel_no_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=False, check_data=True)

            if not data3 or not check_key(data3, 'total'):
                if self._debug_mode:
                    log.debug('Failure to retrieve expected data')
                    log.debug('Execution Done: api.login')

                gui.ok(message=_.LOGIN_ERROR, heading=_.LOGIN_ERROR_TITLE)
                self.clear_session()
                return False

            self.get_channels_for_user(channels=data['channelDetails'], channels_all=data2['channelDetails'], channels_props=data3['channelDynamaicProp'])

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

    def clear_session(self):
        if self._debug_mode:
            log.debug('Executing: api.clear_session')

        settings.remove(key='_cookies')
        self._cookies = ''
        settings.remove(key='_csrf_token')
        self._csrf_token = ''

        try:
            self._session.clear_cookies()

            if self._debug_mode:
                log.debug('Execution Done: api.get_channels_for_user')

            return True
        except:
            if self._debug_mode:
                log.debug('Failure clearing session cookies')
                log.debug('Execution Done: api.get_channels_for_user')

            return False

    def get_channels_for_user(self, channels, channels_all, channels_props):
        if self._debug_mode:
            log.debug('Executing: api.get_channels_for_user')
            log.debug('Vars: channels={channels}, channels_all={channels_all}, channels_props={channels_props}'.format(channels=channels, channels_all=channels_all, channels_props=channels_props))

        write_file(file="channels.json", data=channels, isJSON=True)
        write_file(file="channels_all.json", data=channels_all, isJSON=True)
        write_file(file="channels_props.json", data=channels_props, isJSON=True)

        self.create_playlist()

        if self._debug_mode:
            log.debug('Execution Done: api.get_channels_for_user')

        return True

    def create_playlist(self):
        if self._debug_mode:
            log.debug('Executing: api.create_playlist')

        prefs = load_file(file="channel_prefs.json", isJSON=True)
        channels = load_file(file="channels.json", isJSON=True)
        channels_all = load_file(file="channels_all.json", isJSON=True)
        channels_props = load_file(file="channels_props.json", isJSON=True)

        playlist_all = u'#EXTM3U\n'
        playlist = u'#EXTM3U\n'

        channels_sub_ar = {}

        for row in channels:
            channels_sub_ar[row['ID']] = 1

        channels_props_ar = {}

        for row in channels_props:
            channels_props_ar[row['ID']] = row['channelNO']

        for row in channels_all:
            if row['contentType'] == 'VIDEO_CHANNEL' and check_key(channels_sub_ar, row['ID']):
                channeldata = self.get_channel_data(row=row, channels_no=channels_props_ar[row['ID']])
                id = unicode(channeldata['channel_id'])

                if len(id) > 0:
                    path = 'plugin://{addonid}/?_=play_video&channel={channel}&type=channel&_l=.pvr'.format(addonid=ADDON_ID, channel=channeldata['channel_id'])
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

            if not results:
                results = {}

            for row in channels:
                if count == 5 or (count == 1 and tested):
                    if test_run:
                        self.update_prefs()

                    settings.setBool(key='_test_running', value=False)
                    return count

                channeldata = self.get_channel_data(row=row, channels_no=1)
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

                    playdata = self.play_url(type='channel', channel=id, id=None, test=True)

                    if first and not self._last_login_success:
                        if test_run:
                            self.update_prefs()

                        settings.setBool(key='_test_running', value=False)
                        return 5

                    if len(playdata['path']) > 0:
                        CDMHEADERS = {
                            'User-Agent': user_agent,
                            'X_CSRFToken': self._csrf_token,
                            'Cookie': playdata['license']['cookie'],
                        }

                        if check_key(playdata, 'license') and check_key(playdata['license'], 'triggers') and check_key(playdata['license']['triggers'][0], 'licenseURL'):
                            if check_key(playdata['license']['triggers'][0], 'customData'):
                                CDMHEADERS['AcquireLicense.CustomData'] = playdata['license']['triggers'][0]['customData']
                                CDMHEADERS['CADeviceType'] = 'Widevine OTT client'

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

                    while not self._abortRequested and not xbmc.Monitor().abortRequested() and counter < 5:
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

                    militime = int(int(time.time() - 86400) * 1000)

                    session_post_data = {
                        'needChannel': '0',
                        'queryChannel': {
                            'channelIDs': [
                                id,
                            ],
                            'isReturnAllMedia': '1',
                        },
                        'queryPlaybill': {
                            'count': '1',
                            'endTime': militime,
                            'isFillProgram': '1',
                            'offset': '0',
                            'startTime': militime,
                            'type': '0',
                        }
                    }

                    channel_url = '{base_url}/VSP/V3/QueryPlaybillListStcProps?SID=queryPlaybillListStcProps3&DEVICE=PC&DID={deviceID}&from=throughMSAAccess'.format(base_url=CONST_BASE_URL, deviceID=self._devicekey)
                    data = self.download(url=channel_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=True, check_data=True)

                    if data and check_key(data, 'channelPlaybills') and check_key(data['channelPlaybills'][0], 'playbillLites') and check_key(data['channelPlaybills'][0]['playbillLites'][0], 'ID'):
                        if settings.getInt(key='_last_playing') > int(time.time() - 300):
                            if test_run:
                                self.update_prefs()

                            settings.setBool(key='_test_running', value=False)
                            return 5

                        playdata = self.play_url(type='program', channel=id, id=data['channelPlaybills'][0]['playbillLites'][0]['ID'], test=True)

                        if len(playdata['path']) > 0:
                            CDMHEADERS = {
                                'User-Agent': user_agent,
                                'X_CSRFToken': self._csrf_token,
                                'Cookie': playdata['license']['cookie'],
                            }

                            if check_key(playdata, 'license') and check_key(playdata['license'], 'triggers') and check_key(playdata['license']['triggers'][0], 'licenseURL'):
                                if check_key(playdata['license']['triggers'][0], 'customData'):
                                    CDMHEADERS['AcquireLicense.CustomData'] = playdata['license']['triggers'][0]['customData']
                                    CDMHEADERS['CADeviceType'] = 'Widevine OTT client'

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
            channeldata = self.get_channel_data(row=row, channels_no=1)
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

    def get_channel_data(self, row, channels_no):
        if self._debug_mode:
            log.debug('Executing: api.get_channel_data')
            log.debug('Vars: row={row}, channelno={channelno}'.format(row=row, channelno=channels_no))

        channeldata = {
            'channel_id': '',
            'channel_number': int(channels_no),
            'description': '',
            'label': '',
            'station_image_large': '',
        }

        if not check_key(row, 'ID') or not check_key(row, 'name'):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.get_channel_data')

            return channeldata

        path = ADDON_PROFILE + "images" + os.sep + unicode(row['ID']) + ".png"
        image = ''

        if os.path.isfile(path):
            image = path
        else:
            if check_key(row, 'picture') and check_key(row['picture'], 'icons'):
                image = row['picture']['icons'][0]

        channeldata = {
            'channel_id': row['ID'],
            'channel_number': int(channels_no),
            'description': '',
            'label': row['name'],
            'station_image_large': image
        }

        if self._debug_mode:
            log.debug('Returned data: {channeldata}'.format(channeldata=channeldata))
            log.debug('Execution Done: api.get_channel_data')

        return channeldata

    def play_url(self, type, channel=None, id=None, test=False, from_beginning='False'):
        if self._debug_mode:
            log.debug('Executing: api.play_url')
            log.debug('Vars: type={type}, channel={channel}, id={id}, test={test}'.format(type=type, channel=channel, id=id, test=test))

        mediaID = None
        info = {}
        playdata = {'path': '', 'license': '', 'info': ''}

        if not type or not len(unicode(type)) > 0:
            if self._debug_mode:
                log.debug('Failure executing api.play_url, no type set')
                log.debug('Execution Done: api.play_url')

            return playdata

        if not test:
            while not self._abortRequested and not xbmc.Monitor().abortRequested() and settings.getBool(key='_test_running'):
                settings.setInt(key='_last_playing', value=time.time())

                if self._abortRequested or xbmc.Monitor().waitForAbort(1):
                    self._abortRequested = True
                    break

            if self._abortRequested or xbmc.Monitor().abortRequested():
                return playdata

        militime = int(time.time() * 1000)

        channels_props = load_file(file='channels_props.json', isJSON=True)

        if not type == 'vod':
            mediaID = int(channel) + 1

            for row in channels_props:
                if row['ID'] == channel:
                    mediaID = row['physicalChannelsDynamicProperties'][0]['ID']

        if type == 'channel' and channel:
            if not test:
                session_post_data = {
                    'needChannel': '0',
                    'queryChannel': {
                        'channelIDs': [
                            channel,
                        ],
                        'isReturnAllMedia': '1',
                    },
                    'queryPlaybill': {
                        'count': '1',
                        'endTime': militime,
                        'isFillProgram': '1',
                        'offset': '0',
                        'startTime': militime,
                        'type': '0',
                    }
                }

                channel_url = '{base_url}/VSP/V3/QueryPlaybillListStcProps?SID=queryPlaybillListStcProps3&DEVICE=PC&DID={deviceID}&from=throughMSAAccess'.format(base_url=CONST_BASE_URL, deviceID=self._devicekey)
                data = self.download(url=channel_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=True, check_data=True)

                if not data or not check_key(data, 'channelPlaybills') or not check_key(data['channelPlaybills'][0], 'playbillLites') or not check_key(data['channelPlaybills'][0]['playbillLites'][0], 'ID'):
                    if self._debug_mode:
                        log.debug('Failure to retrieve expected data')
                        log.debug('Execution Done: api.play_url')

                    return playdata

                id = data['channelPlaybills'][0]['playbillLites'][0]['ID']

                session_post_data = {
                    'playbillID': id,
                    'channelNamespace': '310303',
                    'isReturnAllMedia': '1',
                }

                program_url = '{base_url}/VSP/V3/QueryPlaybill?from=throughMSAAccess'.format(base_url=CONST_BASE_URL)
                data = self.download(url=program_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=False, check_data=True)

                if not data or not check_key(data, 'playbillDetail'):
                    if self._debug_mode:
                        log.debug('Failure to retrieve expected data')
                        log.debug('Execution Done: api.play_url')

                    return playdata

                info = data['playbillDetail']

            session_post_data = {
                "businessType": "BTV",
                "channelID": channel,
                "checkLock": {
                    "checkType": "0",
                },
                "isHTTPS": "1",
                "isReturnProduct": "1",
                "mediaID": mediaID,
            }

        elif type == 'program' and id:
            if not test:
                session_post_data = {
                    'playbillID': id,
                    'channelNamespace': '310303',
                    'isReturnAllMedia': '1',
                }

                program_url = '{base_url}/VSP/V3/QueryPlaybill?from=throughMSAAccess'.format(base_url=CONST_BASE_URL)
                data = self.download(url=program_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=True, check_data=True)

                if not data or not check_key(data, 'playbillDetail'):
                    if self._debug_mode:
                        log.debug('Failure to retrieve expected data')
                        log.debug('Execution Done: api.play_url')

                    return playdata

                info = data['playbillDetail']

            session_post_data = {
                "businessType": "CUTV",
                "channelID": channel,
                "checkLock": {
                    "checkType": "0",
                },
                "isHTTPS": "1",
                "isReturnProduct": "1",
                "mediaID": mediaID,
                "playbillID": id,
            }
        elif type == 'vod' and id:
            session_post_data = {
                'VODID': id
            }

            program_url = '{base_url}/VSP/V3/QueryVOD?from=throughMSAAccess'.format(base_url=CONST_BASE_URL)
            data = self.download(url=program_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=True, check_data=True)

            if not data or not check_key(data, 'VODDetail') or not check_key(data['VODDetail'], 'VODType'):
                if self._debug_mode:
                    log.debug('Failure to retrieve expected data')
                    log.debug('Execution Done: api.play_url')

                return playdata

            info = data['VODDetail']

            session_post_data = {
                "VODID": id,
                "checkLock": {
                    "checkType": "0",
                },
                "isHTTPS": "1",
                "isReturnProduct": "1",
                "mediaID": '',
            }

            if check_key(info, 'series') and check_key(info['series'][0], 'VODID'):
                session_post_data["seriesID"] = info['series'][0]['VODID']
                session_post_data["mediaID"] = channel
            else:
                if not check_key(info, 'mediaFiles') or not check_key(info['mediaFiles'][0], 'ID'):
                    if self._debug_mode:
                        log.debug('Failure to retrieve expected data')
                        log.debug('Execution Done: api.play_url')

                    return playdata

                session_post_data["mediaID"] = info['mediaFiles'][0]['ID']

        if not len(unicode(session_post_data["mediaID"])) > 0:
            if self._debug_mode:
                log.debug('Failure, empty id or session_post_data["mediaID"]')
                log.debug('Execution Done: api.play_url')

            return playdata

        if type == 'vod':
            play_url_path = '{base_url}/VSP/V3/PlayVOD?from=throughMSAAccess'.format(base_url=CONST_BASE_URL)
        else:
            play_url_path = '{base_url}/VSP/V3/PlayChannel?from=throughMSAAccess'.format(base_url=CONST_BASE_URL)

        if self._abortRequested or xbmc.Monitor().abortRequested():
            return playdata

        data = self.download(url=play_url_path, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=False, check_data=True)

        if not data or not check_key(data, 'playURL'):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.play_url')

            return playdata

        path = data['playURL']

        if check_key(data, 'authorizeResult'):
            data['authorizeResult']['cookie'] = self.getCookies(self._session.cookies, '')
            license = data['authorizeResult']

        if not test:
            real_url = "{hostscheme}://{netloc}".format(hostscheme=urlparse(path).scheme, netloc=urlparse(path).netloc)
            proxy_url = "http://127.0.0.1:{proxy_port}".format(proxy_port=settings.getInt(key='_proxyserver_port'))

            if self._debug_mode:
                log.debug('Real url: {real_url}'.format(real_url=real_url))
                log.debug('Proxy url: {proxy_url}'.format(proxy_url=proxy_url))

            settings.set(key='_stream_hostname', value=real_url)
            path = path.replace(real_url, proxy_url)

        playdata = {'path': path, 'license': license, 'info': info}

        if self._debug_mode:
            log.debug('Returned Playdata: {playdata}'.format(playdata=playdata))
            log.debug('Execution Done: api.play_url')

        return playdata

    def vod_seasons(self, id):
        if self._debug_mode:
            log.debug('Executing: api.vod_seasons')
            log.debug('Vars: id={id}'.format(id=id))

        seasons = []

        file = "cache" + os.sep + "vod_seasons_" + unicode(id) + ".json"

        if self._enable_cache and not is_file_older_than_x_minutes(file=ADDON_PROFILE + file, minutes=10):
            data = load_file(file=file, isJSON=True)
        else:
            session_post_data = {
                'VODID': unicode(id),
                'offset': '0',
                'count': '50',
            }

            seasons_url = '{base_url}/VSP/V3/QueryEpisodeList?from=throughMSAAccess'.format(base_url=CONST_BASE_URL)
            data = self.download(url=seasons_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=True, check_data=True)

            if data and check_key(data, 'episodes') and self._enable_cache:
                write_file(file=file, data=data, isJSON=True)

        if not data or not check_key(data, 'episodes'):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.vod_seasons')

            return None

        for row in data['episodes']:
            if check_key(row, 'VOD') and check_key(row['VOD'], 'ID') and check_key(row, 'sitcomNO'):
                image = ''

                if check_key(row['VOD'], 'picture') and check_key(row['VOD']['picture'], 'posters'):
                    image = row['VOD']['picture']['posters'][0]

                seasons.append({'id': row['VOD']['ID'], 'seriesNumber': row['sitcomNO'], 'desc': '', 'image': image})

        if self._debug_mode:
            log.debug('Execution Done: api.vod_seasons')

        return seasons

    def vod_season(self, id):
        if self._debug_mode:
            log.debug('Executing: api.vod_season')
            log.debug('Vars: id={id}'.format(id=id))

        season = []

        file = "cache" + os.sep + "vod_season_" + unicode(id) + ".json"

        if self._enable_cache and not is_file_older_than_x_minutes(file=ADDON_PROFILE + file, minutes=10):
            data = load_file(file=file, isJSON=True)
        else:
            session_post_data = {
                'VODID': unicode(id),
                'offset': '0',
                'count': '35',
            }

            seasons_url = '{base_url}/VSP/V3/QueryEpisodeList?from=throughMSAAccess'.format(base_url=CONST_BASE_URL)
            data = self.download(url=seasons_url, type="post", code=[200], data=session_post_data, json_data=True, data_return=True, return_json=True, retry=True, check_data=True)

            if data and check_key(data, 'episodes') and self._enable_cache:
                write_file(file=file, data=data, isJSON=True)

        if not data or not check_key(data, 'episodes'):
            if self._debug_mode:
                log.debug('Failure to retrieve expected data')
                log.debug('Execution Done: api.vod_season')

            return None

        for row in data['episodes']:
            if check_key(row, 'VOD') and check_key(row['VOD'], 'ID') and check_key(row['VOD'], 'name') and check_key(row, 'sitcomNO'):
                image = ''
                duration = 0

                if not check_key(row['VOD'], 'mediaFiles') or not check_key(row['VOD']['mediaFiles'][0], 'ID'):
                    continue

                if check_key(row['VOD']['mediaFiles'][0], 'elapseTime'):
                    duration = row['VOD']['mediaFiles'][0]['elapseTime']

                if check_key(row['VOD'], 'picture') and check_key(row['VOD']['picture'], 'posters'):
                    image = row['VOD']['picture']['posters'][0]

                season.append({'id': row['VOD']['ID'], 'media_id': row['VOD']['mediaFiles'][0]['ID'], 'duration': duration, 'title': row['VOD']['name'], 'episodeNumber': row['sitcomNO'], 'desc': '', 'image': image})

        if self._debug_mode:
            log.debug('Execution Done: api.vod_season')

        return season

    def check_data(self, resp, json=True):
        if self._debug_mode:
            log.debug('Executing: api.check_data')
            log.debug('Vars: resp={resp}, json={json}'.format(resp='Unaltered response, see above', json=json))

        if json:
            data = resp.json()

            if not data or not check_key(data, 'result') or not check_key(data['result'], 'retCode') or not data['result']['retCode'] == '000000000':
                if self._debug_mode:
                    log.debug('Execution Done: api.check_data')

                return False

        if self._debug_mode:
            log.debug('Execution Done: api.check_data')

        return True

    def getCookies(self, cookie_jar, domain):
        cookie_dict = cookie_jar.get_dict(domain=domain)
        found = ['%s=%s' % (name, value) for (name, value) in cookie_dict.items()]
        return '; '.join(found)

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