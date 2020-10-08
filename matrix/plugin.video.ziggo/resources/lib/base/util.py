import collections, glob, hashlib, io, json, os, platform, pytz, re, requests, shutil, string, struct, socket, sys, time, unicodedata, xbmc, xbmcaddon

from contextlib import closing
from resources.lib.base import settings
from resources.lib.base.constants import ADDON_ID, ADDON_PATH, ADDON_PROFILE, DEFAULT_USER_AGENT
from resources.lib.base.encrypt import Credentials
from resources.lib.base.log import log
from resources.lib.constants import CONST_EPG, CONST_IMAGES, CONST_MD5, CONST_MINIMALEPG, CONST_RADIO, CONST_SETTINGS, CONST_VOD

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

try:
    unicode
except NameError:
    unicode = str

from zipfile import ZipFile

debug_mode = settings.getBool(key='enable_debug')

def change_icon():
    try:
        settingsJSON = load_file(file='settings.json', isJSON=True)

        if check_key(settingsJSON, 'icon') and check_key(settingsJSON['icon'], 'md5'):
            addon_icon = ADDON_PATH + os.sep + "icon.png"

            if debug_mode:
                log.debug('ICON settings key and MD5 found')
                log.debug('ICON settings MD5: {mdfive}'.format(mdfive=settingsJSON['icon']['md5']))
                log.debug('Addon path icon.png MD5: {mdfive}'.format(mdfive=md5sum(addon_icon)))

            if not md5sum(addon_icon) or settingsJSON['icon']['md5'] != md5sum(addon_icon):
                if debug_mode:
                    log.debug('No icon.png found in Addon Path or ICON settings MD5 does not match Addon Path icon.png MD5, attempting to change ICON')
                    log.debug('Downloading ICON from {url}'.format(url=settingsJSON['icon']['url']))

                r = requests.get(settingsJSON['icon']['url'], stream=True)

                if r.status_code == 200:
                    if debug_mode:
                        log.debug('Trying to write ICON to {addon_path}'.format(addon_path=addon_icon))

                    try:
                        with open(addon_icon, 'wb') as f:
                            for chunk in r.iter_content(1024):
                                f.write(chunk)

                        if debug_mode:
                            log.debug('Succesfully written ICON to {addon_path}'.format(addon_path=addon_icon))
                    except:
                        if debug_mode:
                            log.debug('Error while writing ICON to {addon_path}'.format(addon_path=addon_icon))

                        return False
                else:
                    if debug_mode:
                        log.debug('Error trying to download ICON from url, Status code: {code}'.format(code=r.status_code))

                    return False

                try:
                    from sqlite3 import dbapi2 as sqlite3

                    if debug_mode:
                        log.debug('SQLite imported from SQLite3')
                except:
                    from pysqlite2 import dbapi2 as sqlite

                    if debug_mode:
                        log.debug('SQLite imported from PySQLite2')

                try:
                    texture_file = 'Textures13.db'

                    for file in glob.glob(xbmc.translatePath("special://database") + os.sep + "*Textures*"):
                        texture_file = file

                    if debug_mode:
                        log.debug('Texture File: {texture}'.format(texture=texture_file))

                    DB = os.path.join(xbmc.translatePath("special://database"), texture_file)

                    if debug_mode:
                        log.debug('Texture File Path: {texture}'.format(texture=DB))

                    db = sqlite.connect(DB)
                    query = "SELECT cachedurl FROM texture WHERE url LIKE '%addons%" + ADDON_ID + "%icon.png';"

                    if debug_mode:
                        log.debug('DB Query: {query}'.format(query=query))

                    rows = db.execute(query)

                    for row in rows:
                        thumb = os.path.join(xbmc.translatePath("special://thumbnails"), unicode(row[0]))

                        if debug_mode:
                            log.debug('Thumb Found: {thumb}'.format(thumb=thumb))

                        if os.path.isfile(thumb):
                            os.remove(thumb)

                            if debug_mode:
                                log.debug('Thumb Removed: {thumb}'.format(thumb=thumb))

                    query = "DELETE FROM texture WHERE url LIKE '%addons%" + ADDON_ID + "%icon.png';"

                    if debug_mode:
                        log.debug('DB Query: {query}'.format(query=query))

                    db.execute(query)
                    db.commit()
                    db.close()

                    if debug_mode:
                        log.debug('DB Queries completed, changing addon done')
                        log.debug('ICON settings MD5: {mdfive}'.format(mdfive=settingsJSON['icon']['md5']))
                        log.debug('Addon Path icon.png MD5: {mdfive}'.format(mdfive=md5sum(ADDON_PATH + "icon.png")))
                except:
                    return False
            else:
                if debug_mode:
                    log.debug('ICON settings MD5 matches Addon Path icon.png MD5, skipping')
        else:
            if debug_mode:
                log.debug('ICON settings key not found')
    except:
        if debug_mode:
            log.debug('Exception while trying to change ICON')

def check_iptv_link():
    if settings.getBool(key='enable_simple_iptv') == True:
        try:
            IPTV_SIMPLE = xbmcaddon.Addon(id="pvr.iptvsimple")

            if not IPTV_SIMPLE.getSetting("epgPath") == (ADDON_PROFILE + "epg.xml") or not IPTV_SIMPLE.getSetting("m3uPath") == (ADDON_PROFILE + "playlist.m3u8"):
                settings.setBool(key='enable_simple_iptv', value=False)
            else:
                user_agent = settings.get(key='_user_agent')

                if IPTV_SIMPLE.getSetting("userAgent") != user_agent:
                    IPTV_SIMPLE.setSetting("userAgent", user_agent)
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

    if settings.getBool(key='enable_radio') == True:
        radio = load_file(file='radio.m3u8', isJSON=False)

    if not radio:
        radio = ''

    write_file(file='playlist.m3u8', data=tv + radio, isJSON=False)

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
    settings.setInt(key='_epgrun', value=1)
    settings.setInt(key='_epgruntime', value=time.time())

    if settings.getBool(key="minimalChannels"):
        url = CONST_MINIMALEPG
    else:
        url = CONST_EPG

    if ADDON_ID == "plugin.video.ziggo" and settings.getBool(key='_base_v3') == True:
        url = url.replace('epg.xml.', 'epg.xml.v3.')

    resp = requests.get(url=url)

    settings.set(key='_epg_md5', value=hashlib.md5(resp.content).hexdigest())

    zipfile = ZipFile(BytesIO(resp.content))
    zipfile.extractall(ADDON_PROFILE)
    zipfile.close()

    for file in glob.glob(ADDON_PROFILE + "*_replay.xml"):
        if is_file_older_than_x_days(file=file, days=7):
            os.remove(file)

    for file in glob.glob(ADDON_PROFILE + "*_replay.json"):
        if is_file_older_than_x_days(file=file, days=7):
            os.remove(file)

    settings.setInt("_epgrun", 0)

def download_files():
    download_mdfive()
    renew_images()
    renew_settings()
    renew_epg()
    renew_vod()

def download_images():
    resp = requests.get(url=CONST_IMAGES)

    settings.set(key='_images_md5', value=hashlib.md5(resp.content).hexdigest())

    zipfile = ZipFile(BytesIO(resp.content))
    zipfile.extractall(ADDON_PROFILE)
    zipfile.close()

    for file in glob.glob(ADDON_PROFILE + "images" + os.sep + "*.png"):
        if is_file_older_than_x_days(file=file, days=7):
            os.remove(file)

def download_mdfive():
    resp = requests.get(url=CONST_MD5)
    write_file(file='md5.json', data=resp.text, isJSON=False)

def download_settings():
    resp = requests.get(url=CONST_SETTINGS)
    write_file(file='settings.json', data=resp.text, isJSON=False)

    if settings.getBool(key='enable_radio') == True:
        resp = requests.get(url=CONST_RADIO)
        write_file(file='radio.m3u8', data=resp.text, isJSON=False)
        combine_playlist()

    settingsJSON = load_file(file='settings.json', isJSON=True)

    try:
        settings.set(key='_user_agent', value=settingsJSON['user_agent'])
    except:
        settings.set(key='_user_agent', value=DEFAULT_USER_AGENT)

def download_vod():
    url = CONST_VOD

    if ADDON_ID == "plugin.video.ziggo" and settings.getBool(key='_base_v3') == True:
        url = url.replace('vod.', 'vod.v3.')

    resp = requests.get(url=url)
    write_file(file='vod.json', data=resp.text, isJSON=False)

    settings.set(key='_vod_md5', value=hashlib.md5(resp.content).hexdigest())

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
    username = settings.get(key='_username')
    password = settings.get(key='_pswd')

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

def md5sum(filepath):
    if not os.path.isfile(filepath):
        return None

    return hashlib.md5(open(filepath,'rb').read()).hexdigest()

def renew_images():
    md5JSON = load_file(file='md5.json', isJSON=True)

    try:
        if settings.get(key='_epg_md5') != md5JSON['images.zip']:
            download_images()
    except:
        download_images()

def renew_epg():
    md5JSON = load_file(file='md5.json', isJSON=True)

    if settings.getInt(key='_epgrun') == 0 or settings.getInt(key='_epgruntime') < (int(time.time()) - 300):
        try:
            if settings.getBool(key="minimalChannels"):
                if ADDON_ID == "plugin.video.ziggo" and settings.getBool(key='_base_v3') == True:
                    key = 'epg.xml.v3.minimal.zip'
                else:
                    key = 'epg.xml.minimal.zip'
            else:
                if ADDON_ID == "plugin.video.ziggo" and settings.getBool(key='_base_v3') == True:
                    key = 'epg.xml.v3.zip'
                else:
                    key = 'epg.xml.zip'

            if settings.get(key='_epg_md5') != md5JSON[key]:
                download_epg()
        except:
            download_epg()

def renew_settings():
    if is_file_older_than_x_days(file=ADDON_PROFILE + "settings.json", days=1):
        download_settings()

def renew_vod():
    if settings.getBool(key='showMoviesSeries') == True:
        md5JSON = load_file(file='md5.json', isJSON=True)

        try:
            if ADDON_ID == "plugin.video.ziggo" and settings.getBool(key='_base_v3') == True:
                key = 'vod.v3.json'
            else:
                key = 'vod.json'

            if settings.get(key='_vod_md5') != md5JSON[key]:
                download_vod()
        except:
            download_vod()

def set_credentials(username, password):
    encoded = Credentials().encode_credentials(username, password)

    try:
        settings.set(key='_username', value=encoded['username'].decode('utf-8'))
    except:
        settings.set(key='_username', value=encoded['username'])

    try:
        settings.set(key='_pswd', value=encoded['password'].decode('utf-8'))
    except:
        settings.set(key='_pswd', value=encoded['password'])

def set_duration(xml):
    try:
        duration = settings.getInt(key='_stream_duration')

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

def write_file(file, data, isJSON=False):
    with io.open(ADDON_PROFILE + file, 'w', encoding="utf-8") as f:
        if isJSON == True:
            f.write(unicode(json.dumps(data, ensure_ascii=False)))
        else:
            f.write(unicode(data))