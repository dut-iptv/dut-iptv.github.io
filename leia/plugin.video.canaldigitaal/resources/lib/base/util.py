import collections, glob, hashlib, io, json, os, platform, pytz, re, requests, shutil, string, struct, socket, sys, time, unicodedata, xbmc, xbmcaddon

from contextlib import closing
from resources.lib.base import settings
from resources.lib.base.constants import ADDON_ID, ADDON_PATH, ADDON_PROFILE, DEFAULT_USER_AGENT, EPG_DB_FILE, SETTINGS_DB_FILE
from resources.lib.base.encrypt import Credentials
from resources.lib.base.log import log
from resources.lib.constants import CONST_EPG, CONST_IMAGES, CONST_MD5, CONST_MINIMALEPG, CONST_RADIO, CONST_SETTINGS, SETUP_DB_QUERIES
from zipfile import ZipFile

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

try:
    unicode
except NameError:
    unicode = str

try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite

def change_icon():
    try:
        settingsJSON = load_file(file='settings.json', isJSON=True)

        if check_key(settingsJSON, 'icon') and check_key(settingsJSON['icon'], 'md5'):
            addon_icon = ADDON_PATH + os.sep + "icon.png"

            if not md5sum(addon_icon) or settingsJSON['icon']['md5'] != md5sum(addon_icon):
                r = requests.get(settingsJSON['icon']['url'], stream=True)

                if r.status_code == 200:
                    if debug_mode:
                        log.debug('Trying to write ICON to {addon_path}'.format(addon_path=addon_icon))

                    try:
                        with open(addon_icon, 'wb') as f:
                            for chunk in r.iter_content(1024):
                                f.write(chunk)
                    except:
                        return False
                else:
                    return False

                try:
                    texture_file = 'Textures13.db'

                    for file in glob.glob(xbmc.translatePath("special://database") + os.sep + "*Textures*"):
                        texture_file = file

                    DB = os.path.join(xbmc.translatePath("special://database"), texture_file)

                    db = sqlite.connect(DB)
                    query = "SELECT cachedurl FROM texture WHERE url LIKE '%addons%" + ADDON_ID + "%icon.png';"

                    rows = db.execute(query)

                    for row in rows:
                        thumb = os.path.join(xbmc.translatePath("special://thumbnails"), unicode(row[0]))

                        if os.path.isfile(thumb):
                            os.remove(thumb)

                    query = "DELETE FROM texture WHERE url LIKE '%addons%" + ADDON_ID + "%icon.png';"

                    db.execute(query)
                    db.commit()
                    db.close()
                except:
                    return False
    except:
        pass

def check_iptv_link():
    if settings.getBool(key='enable_simple_iptv'):
        try:
            IPTV_SIMPLE = xbmcaddon.Addon(id="pvr.iptvsimple")

            if not IPTV_SIMPLE.getSetting("epgPath") == (ADDON_PROFILE + "epg.xml") or not IPTV_SIMPLE.getSetting("m3uPath") == (ADDON_PROFILE + "playlist.m3u8"):
                settings.setBool(key='enable_simple_iptv', value=False)
            else:
                profile_settings = load_profile(profile_id=1)

                if IPTV_SIMPLE.getSetting("userAgent") != profile_settings['user_agent']:
                    IPTV_SIMPLE.setSetting("userAgent", profile_settings['user_agent'])
        except:
            pass

def check_key(object, key):
    if key in object and object[key] and len(unicode(object[key])) > 0:
        return True
    else:
        return False

def clean_filename(filename):
    for r in ' ':
        filename = filename.replace(r,'_')

    cleaned_filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode()
    whitelist = "-_.() %s%s" % (string.ascii_letters, string.digits)

    cleaned_filename = ''.join(c for c in cleaned_filename if c in whitelist)

    return cleaned_filename[:255]

def clear_cache():
    if not os.path.isdir(ADDON_PROFILE + "cache"):
        os.makedirs(ADDON_PROFILE + "cache")

    for file in glob.glob(ADDON_PROFILE + "cache" + os.sep + "*.json"):
        if is_file_older_than_x_days(file=file, days=1):
            os.remove(file)

def combine_playlist():
    tv = load_file(file='tv.m3u8', isJSON=False)

    if not tv:
        tv = u'#EXTM3U\n'

    radio = None

    if settings.getBool(key='enable_radio'):
        radio = load_file(file='radio.m3u8', isJSON=False)

    if not radio:
        radio = ''

    write_file(file='playlist.m3u8', data=tv + radio, isJSON=False)

def create_playlist():
    prefs = load_prefs(profile_id=1)

    query = "SELECT * FROM `channels`"
    channels = query_epg(query=query, return_result=True, return_insert=False, commit=False)

    playlist_all = u'#EXTM3U\n'
    playlist = u'#EXTM3U\n'

    for row in channels:
        id = unicode(row['id'])

        if len(id) > 0:
            path = ADDON_PROFILE + "images" + os.sep + unicode(row['id']) + ".png"

            if os.path.isfile(path):
                image = path
            else:
                image = row['icon']

            path = 'plugin://{addonid}/?_=play_video&channel={channel}&id={asset}&type=channel&_l=.pvr'.format(addonid=ADDON_ID, channel=row['id'], asset=row['assetid'])
            playlist_all += u'#EXTINF:-1 tvg-id="{id}" tvg-chno="{channel}" tvg-name="{name}" tvg-logo="{logo}" group-title="TV" radio="false",{name}\n{path}\n'.format(id=row['id'], channel=row['channelno'], name=row['name'], logo=image, path=path)

            if not prefs or not check_key(prefs, id) or prefs[id]['epg'] == 1:
                playlist += u'#EXTINF:-1 tvg-id="{id}" tvg-chno="{channel}" tvg-name="{name}" tvg-logo="{logo}" group-title="TV" radio="false",{name}\n{path}\n'.format(id=row['id'], channel=row['channelno'], name=row['name'], logo=image, path=path)

    write_file(file="tv.m3u8", data=playlist, isJSON=False)
    write_file(file="tv_all.m3u8", data=playlist_all, isJSON=False)
    combine_playlist()

def convert_datetime_timezone(dt, tz1, tz2):
    tz1 = pytz.timezone(tz1)
    tz2 = pytz.timezone(tz2)

    dt = tz1.localize(dt)
    dt = dt.astimezone(tz2)

    return dt

def date_to_nl_dag(curdate):
    dag = {
        "Mon": "Maandag",
        "Tue": "Dinsdag",
        "Wed": "Woensdag",
        "Thu": "Donderdag",
        "Fri": "Vrijdag",
        "Sat": "Zaterdag",
        "Sun": "Zondag"
    }

    return dag.get(curdate.strftime("%a"), "")

def date_to_nl_maand(curdate):
    maand = {
        "January": "januari",
        "February": "februari",
        "March": "maart",
        "April": "april",
        "May": "mei",
        "June": "juni",
        "July": "juli",
        "August": "augustus",
        "September": "september",
        "October": "oktober",
        "November": "november",
        "December": "Vrijdag"
    }

    return maand.get(curdate.strftime("%B"), "")

def download_epg():
    query = "UPDATE `vars` SET `epgrun`='{epgrun}', `epgruntime`='{epgruntime}' WHERE profile_id={profile_id}".format(epgrun=1, epgruntime=int(time.time()), profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)

    if settings.getBool(key="minimalChannels"):
        url = CONST_MINIMALEPG
    else:
        url = CONST_EPG

    if ADDON_ID == "plugin.video.ziggo":
        profile_settings = load_profile(profile_id=1)

        if int(profile_settings['base_v3']) == 1:
            url = url.replace('epg.db.', 'epg.db.v3.')

    resp = requests.get(url=url)

    zipfile = ZipFile(BytesIO(resp.content))
    zipfile.extractall(ADDON_PROFILE)
    zipfile.close()

    for file in glob.glob(ADDON_PROFILE + "*_replay.xml"):
        if is_file_older_than_x_days(file=file, days=7):
            os.remove(file)

    for file in glob.glob(ADDON_PROFILE + "*_replay.json"):
        if is_file_older_than_x_days(file=file, days=7):
            os.remove(file)

    query = "UPDATE `vars` SET `epgrun`='{epgrun}', `epg_md5`='{epg_md5}' WHERE profile_id={profile_id}".format(epgrun=0, epg_md5=hashlib.md5(resp.content).hexdigest(), profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)

def download_files():
    resp = requests.get(url=CONST_MD5)
    write_file(file='md5.json', data=resp.text, isJSON=False)

    profile_settings = load_profile(profile_id=1)

    if is_file_older_than_x_days(file=ADDON_PROFILE + "settings.json", days=1):
        download_settings()

    md5JSON = load_file(file='md5.json', isJSON=True)

    if int(profile_settings['epgrun']) == 0 or int(profile_settings['epgruntime']) < (int(time.time()) - 300):
        try:
            if settings.getBool(key="minimalChannels"):
                if ADDON_ID == "plugin.video.ziggo" and int(profile_settings['base_v3']) == 1:
                    key = 'epg.db.v3.minimal.zip'
                else:
                    key = 'epg.db.minimal.zip'
            else:
                if ADDON_ID == "plugin.video.ziggo" and int(profile_settings['base_v3']) == 1:
                    key = 'epg.db.v3.zip'
                else:
                    key = 'epg.db.zip'

            if len(profile_settings['epg_md5']) == 0 or profile_settings['epg_md5'] != md5JSON[key]:
                download_epg()
        except:
            download_epg()

    try:
        if len(profile_settings['images_md5']) == 0 or profile_settings['images_md5'] != md5JSON['images.zip']:
            download_images()
    except:
        download_images()

def download_images():
    resp = requests.get(url=CONST_IMAGES)

    query = "UPDATE `vars` SET `images_md5`='{images_md5}' WHERE profile_id={profile_id}".format(images_md5=hashlib.md5(resp.content).hexdigest(), profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)

    zipfile = ZipFile(BytesIO(resp.content))
    zipfile.extractall(ADDON_PROFILE)
    zipfile.close()

    for file in glob.glob(ADDON_PROFILE + "images" + os.sep + "*.png"):
        if is_file_older_than_x_days(file=file, days=7):
            os.remove(file)

def download_settings():
    resp = requests.get(url=CONST_SETTINGS)
    write_file(file='settings.json', data=resp.text, isJSON=False)

    if settings.getBool(key='enable_radio'):
        resp = requests.get(url=CONST_RADIO)
        write_file(file='radio.m3u8', data=resp.text, isJSON=False)
        combine_playlist()

    settingsJSON = load_file(file='settings.json', isJSON=True)

    try:
        user_agent = settingsJSON['user_agent']
    except:
        user_agent = DEFAULT_USER_AGENT

    query = "UPDATE `vars` SET `user_agent`='{user_agent}' WHERE profile_id={profile_id}".format(user_agent=user_agent, profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)

def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

def find_highest_bandwidth(xml):
    bandwidth = 0

    result = re.findall(r'<[rR]epresentation(?:(?!<[rR]epresentation)(?!</[aA]daptationSet>)[\S\s])+', xml)
    bandwidth_regex = r"bandwidth=\"([0-9]+)\""

    for match in result:
        if not 'id="video' in match and not 'id="Video' in match:
            continue

        match2 = re.search(bandwidth_regex, match)

        if match2:
            try:
                if int(match2.group(1)) > bandwidth:
                    bandwidth = int(match2.group(1))
            except:
                pass

    return bandwidth

def force_highest_bandwidth(xml):
    try:
        results = {}

        result = re.findall(r'<[rR]epresentation(?:(?!<[rR]epresentation)(?!</[aA]daptationSet>)[\S\s])+', xml)
        bandwidth_regex = r"bandwidth=\"([0-9]+)\""

        for match in result:
            if not 'id="video' in match and not 'id="Video' in match:
                continue

            bandwidth = 0
            match2 = re.search(bandwidth_regex, match)

            if match2:
                bandwidth = match2.group(1)

            results[bandwidth] = match

        if len(results) > 1:
            results.pop(max(results, key=int))

        for bandwidth in results:
            xml = xml.replace(results[bandwidth], "")

    except:
        pass

    return xml

def get_credentials():
    profile_settings = load_profile(profile_id=1)
    username = profile_settings['username']
    password = profile_settings['pswd']

    if len(username) < 50 and len(password) < 50:
        set_credentials(username, password)
        return {'username' : username, 'password' : password }

    return Credentials().decode_credentials(username, password)

def get_kodi_version():
    try:
        return int(xbmc.getInfoLabel("System.BuildVersion").split('.')[0])
    except:
        return 0

def get_system_arch():
    if xbmc.getCondVisibility('System.Platform.UWP') or '4n2hpmxwrvr6p' in xbmc.translatePath('special://xbmc/'):
        system = 'UWP'
    elif xbmc.getCondVisibility('System.Platform.Android'):
        system = 'Android'
    elif xbmc.getCondVisibility('System.Platform.IOS'):
        system = 'IOS'
    else:
        system = platform.system()

    if system == 'Windows':
        arch = platform.architecture()[0]
    else:
        try:
            arch = platform.machine()
        except:
            arch = ''

    #64bit kernel with 32bit userland
    if ('aarch64' in arch or 'arm64' in arch) and (struct.calcsize("P") * 8) == 32:
        arch = 'armv7'

    elif 'arm' in arch:
        if 'v6' in arch:
            arch = 'armv6'
        else:
            arch = 'armv7'

    elif arch == 'i686':
        arch = 'i386'

    return system, arch

def is_file_older_than_x_days(file, days=1):
    if not os.path.isfile(file):
        return True

    file_time = os.path.getmtime(file)
    totaltime = int(time.time()) - int(file_time)
    totalhours = float(totaltime) / float(3600)

    if totalhours > 24*days:
        return True
    else:
        return False

def is_file_older_than_x_minutes(file, minutes=1):
    if not os.path.isfile(file):
        return True

    file_time = os.path.getmtime(file)
    totaltime = int(time.time()) - int(file_time)
    totalminutes = float(totaltime) / float(60)

    if totalminutes > minutes:
        return True
    else:
        return False

def load_file(file, isJSON=False):
    if not os.path.isfile(ADDON_PROFILE + file):
        file = re.sub(r'[^a-z0-9.]+', '_', file).lower()

        if not os.path.isfile(ADDON_PROFILE + file):
            return None

    with io.open(ADDON_PROFILE + file, 'r', encoding='utf-8') as f:
        if isJSON == True:
            return json.load(f, object_pairs_hook=collections.OrderedDict)
        else:
            return f.read()

def load_prefs(profile_id=1):
    query = "SELECT * FROM `prefs_{profile_id}`".format(profile_id=int(profile_id))
    result = query_settings(query=query, return_result=True, return_insert=False, commit=False)

    return_result = {}

    for row in result:
        return_result[unicode(row['id'])] = dict(row)

    return return_result

def load_profile(profile_id=1):
    query = "SELECT * FROM `vars` WHERE `profile_id`='{id}'".format(id=int(profile_id))
    result = query_settings(query=query, return_result=True, return_insert=False, commit=False)

    if not result or len(result) < 1:
        pswd = settings.get(key='_pswd')
        username = settings.get(key='_username')

        create_query = '''CREATE TABLE IF NOT EXISTS `prefs_{profile_id}` (
            `id` INT(11) PRIMARY KEY,
            `live` TINYINT(1) DEFAULT 1,
            `live_auto` TINYINT(1) DEFAULT 1,
            `replay` TINYINT(1) DEFAULT 1,
            `replay_auto` TINYINT(1) DEFAULT 1,
            `epg` TINYINT(1) DEFAULT 1,
            `epg_auto` TINYINT(1) DEFAULT 1
        )'''.format(profile_id=int(profile_id))

        result = query_settings(query=create_query, return_result=False, return_insert=True, commit=True)

        create_query = '''CREATE TABLE IF NOT EXISTS `tests_{profile_id}` (
            `id` VARCHAR(255) PRIMARY KEY,
            `live` TINYINT(1) DEFAULT 1,
            `livebandwidth` INT(11) DEFAULT NULL,
            `replay` TINYINT(1) DEFAULT 1,
            `replaybandwidth` INT(11) DEFAULT NULL,
            `epg` TINYINT(1) DEFAULT 1,
            `guide` TINYINT(1) DEFAULT 1
        )'''.format(profile_id=int(profile_id))

        result = query_settings(query=create_query, return_result=False, return_insert=True, commit=True)

        add_query = "INSERT INTO `vars` (`profile_id`, `pswd`, `username`) VALUES ('{id}', '{pswd}', '{username}')".format(id=int(profile_id), pswd=pswd, username=username)
        result = query_settings(query=add_query, return_result=False, return_insert=True, commit=True)

        if result and result == profile_id:
            result = query_settings(query=query, return_result=True, return_insert=False, commit=False)

            if not result or len(result) < 1:
                return None

    return result[0]

def load_tests(profile_id=1):
    query = "SELECT * FROM `tests_{profile_id}`".format(profile_id=int(profile_id))
    result = query_settings(query=query, return_result=True, return_insert=False, commit=False)

    return_result = {}

    for row in result:
        return_result[unicode(row['id'])] = dict(row)

    return return_result

def md5sum(filepath):
    if not os.path.isfile(filepath):
        return None

    return hashlib.md5(open(filepath,'rb').read()).hexdigest()

def query_epg(query, return_result=True, return_insert=False, commit=False):
    return query_db(db_file=EPG_DB_FILE, query=query, return_result=return_result, return_insert=return_insert, commit=commit)

def query_settings(query, return_result=True, return_insert=False, commit=False):
    return query_db(db_file=SETTINGS_DB_FILE, query=query, return_result=return_result, return_insert=return_insert, commit=commit)

def query_db(db_file, query, return_result=True, return_insert=False, commit=False):
    if not os.path.isfile(db_file):
        if db_file == SETTINGS_DB_FILE:
            db = sqlite.connect(db_file)
            cur = db.cursor()

            for setup_query in SETUP_DB_QUERIES:
                cur.execute(setup_query)

            db.commit()
        elif db_file == EPG_DB_FILE:
            while not xbmc.Monitor().abortRequested() and not os.path.isfile(db_file):
                download_files()

                if xbmc.Monitor().waitForAbort(1):
                    break

            db = sqlite.connect(db_file)
    else:
        db = sqlite.connect(db_file)

    result = None

    with db:
        db.row_factory = sqlite.Row

        cur = db.cursor()
        cur.execute(query)

        if return_result:
            result = cur.fetchall()

        if return_insert:
            result = cur.lastrowid

        if commit:
            db.commit()

    db.close()

    return result

def set_credentials(username, password):
    encoded = Credentials().encode_credentials(username, password)

    try:
        username = encoded['username'].decode('utf-8')
    except:
        username = encoded['username']

    try:
        pswd = encoded['password'].decode('utf-8')
    except:
        pswd = encoded['password']

    query = "UPDATE `vars` SET `pswd`='{pswd}', `username`='{username}' WHERE profile_id={profile_id}".format(pswd=pswd, username=username, profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)

def set_duration(xml):
    try:
        profile_settings = load_profile(profile_id=1)
        duration = profile_settings['stream_duration']

        if duration and duration > 0:
            given_duration = 0
            matched = False
            duration += settings.getInt(key='add_duration')

            regex = r"mediaPresentationDuration=\"PT([0-9]*)M([0-9]*)[0-9.]*S\""
            matches2 = re.finditer(regex, xml, re.MULTILINE)

            if len([i for i in matches2]) > 0:
                matches = re.finditer(regex, xml, re.MULTILINE)
                matched = True
            else:
                regex2 = r"mediaPresentationDuration=\"PT([0-9]*)H([0-9]*)M([0-9]*)[0-9.]*S\""
                matches3 = re.finditer(regex2, xml, re.MULTILINE)

                if len([i for i in matches3]) > 0:
                    matches = re.finditer(regex2, xml, re.MULTILINE)
                    matched = True
                else:
                    regex3 = r"mediaPresentationDuration=\"PT([0-9]*)D([0-9]*)H([0-9]*)M([0-9]*)[0-9.]*S\""
                    matches4 = re.finditer(regex3, xml, re.MULTILINE)

                    if len([i for i in matches4]) > 0:
                        matches = re.finditer(regex3, xml, re.MULTILINE)
                        matched = True

            if matched == True:
                given_day = 0
                given_hour = 0
                given_minute = 0
                given_second = 0

                for matchNum, match in enumerate(matches, start=1):
                    if len(match.groups()) == 2:
                        given_minute = int(match.group(1))
                        given_second = int(match.group(2))
                    elif len(match.groups()) == 3:
                        given_hour = int(match.group(1))
                        given_minute = int(match.group(2))
                        given_second = int(match.group(3))
                    elif len(match.groups()) == 4:
                        given_day = int(match.group(1))
                        given_hour = int(match.group(2))
                        given_minute = int(match.group(3))
                        given_second = int(match.group(4))

                given_duration = (given_day * 24* 60 * 60) + (given_hour * 60 * 60) + (given_minute * 60) + given_second

            if not given_duration > 0 or given_duration > duration:
                minute, second = divmod(duration, 60)
                hour, minute = divmod(minute, 60)

                regex4 = r"mediaPresentationDuration=\"[a-zA-Z0-9.]*\""
                subst = "mediaPresentationDuration=\"PT{hour}H{minute}M{second}S\"".format(hour=hour, minute=minute, second=second)
                regex5 = r"duration=\"[a-zA-Z0-9.]*\">"
                subst2 = "duration=\"PT{hour}H{minute}M{second}S\">".format(hour=hour, minute=minute, second=second)

                xml = re.sub(regex4, subst, xml, 0, re.MULTILINE)
                xml = re.sub(regex5, subst2, xml, 0, re.MULTILINE)
    except:
        pass

    return xml

def update_prefs():
    prefs = load_prefs(profile_id=1)
    results = load_tests(profile_id=1)

    query = "SELECT * FROM `channels`"
    data = query_epg(query=query, return_result=True, return_insert=False, commit=False)

    for row in data:
        id = unicode(row['id'])

        if len(id) == 0:
            continue

        keys = ['live', 'replay', 'epg']
        mod_pref = {
            'live': 1,
            'live_auto': 1,
            'replay': 1,
            'replay_auto': 1,
            'epg': 1,
            'epg_auto': 1,
        }

        for key in keys:
            if not prefs or not check_key(prefs, id) or not check_key(prefs[id], key):
                if not results or not check_key(results, id):
                    mod_pref[key] = 1
                    mod_pref[key + '_auto'] = 1
                else:
                    result_value = results[id][key]
                    mod_pref[key] = result_value
                    mod_pref[key + '_auto'] = 1
            elif prefs[id][key + '_auto'] == 1 and results and check_key(results, id):
                mod_pref[key] = results[id][key]

        query = "REPLACE INTO `prefs_{profile_id}` VALUES ('{id}', '{live}', '{live_auto}', '{replay}', '{replay_auto}', '{epg_auto}', '{epg_auto}')".format(profile_id=1, id=id, live=mod_pref['live'], live_auto=mod_pref['live_auto'], replay=mod_pref['replay'], replay_auto=mod_pref['replay_auto'], epg=mod_pref['epg'], epg_auto=mod_pref['epg_auto'])
        query_settings(query=query, return_result=False, return_insert=False, commit=True)

def write_file(file, data, isJSON=False):
    with io.open(ADDON_PROFILE + file, 'w', encoding="utf-8") as f:
        if isJSON == True:
            f.write(unicode(json.dumps(data, ensure_ascii=False)))
        else:
            f.write(unicode(data))