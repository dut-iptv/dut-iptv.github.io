import _strptime

import datetime, json, os, pytz, random, string, sys, time, uuid, xbmc, xbmcplugin

from fuzzywuzzy import fuzz
from resources.lib.api import API
from resources.lib.base import plugin, gui, signals, inputstream, settings
from resources.lib.base.constants import ADDON_ID, ADDON_PROFILE
from resources.lib.base.exceptions import Error
from resources.lib.base.log import log
from resources.lib.base.util import check_key, convert_datetime_timezone, create_playlist, date_to_nl_dag, date_to_nl_maand, get_credentials, load_file, load_prefs, load_profile, load_tests, query_epg, query_settings, set_credentials, write_file
from resources.lib.constants import CONST_BASE_HEADERS
from resources.lib.language import _

try:
    unicode
except NameError:
    unicode = str

try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite

api = API()
api._abortRequested = False
backend = ''

@plugin.route('')
def home(**kwargs):
    profile_settings = load_profile(profile_id=1)

    if profile_settings['first_boot'] == 1:
        first_boot()

    folder = plugin.Folder()

    if len(profile_settings['pswd']) > 0:
        folder.add_item(label=_(_.LIVE_TV, _bold=True),  path=plugin.url_for(func_or_url=live_tv))
        folder.add_item(label=_(_.CHANNELS, _bold=True), path=plugin.url_for(func_or_url=replaytv))

        if settings.getBool('showMoviesSeries'):
            folder.add_item(label=_(_.SERIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='series', label=_.SERIES, start=0))
            folder.add_item(label=_(_.MOVIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='movies', label=_.MOVIES, start=0))
            folder.add_item(label=_(_.KIDS_SERIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='kidsseries', label=_.KIDS_SERIES, start=0))
            folder.add_item(label=_(_.KIDS_MOVIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='kidsmovies', label=_.KIDS_MOVIES, start=0))

        folder.add_item(label=_(_.SEARCH, _bold=True), path=plugin.url_for(func_or_url=search_menu))

    folder.add_item(label=_(_.LOGIN, _bold=True), path=plugin.url_for(func_or_url=login))
    folder.add_item(label=_.SETTINGS, path=plugin.url_for(func_or_url=settings_menu))

    return folder

#Main menu items
@plugin.route()
def login(ask=True, **kwargs):
    profile_settings = load_profile(profile_id=1)

    if len(profile_settings['devicekey']) == 0:
        _devicekey = 'w{uuid}'.format(uuid=uuid.uuid4())
        query = "UPDATE `vars` SET `devicekey`='{devicekey}' WHERE profile_id={profile_id}".format(devicekey=_devicekey, profile_id=1)
        query_settings(query=query, return_result=False, return_insert=False, commit=True)

    creds = get_credentials()

    if len(creds['username']) < 1 or len(creds['password']) < 1 or ask:
        username = gui.input(message=_.ASK_USERNAME, default=creds['username']).strip()

        if not len(username) > 0:
            gui.ok(message=_.EMPTY_USER, heading=_.LOGIN_ERROR_TITLE)
            return

        password = gui.input(message=_.ASK_PASSWORD, hide_input=True).strip()

        if not len(password) > 0:
            gui.ok(message=_.EMPTY_PASS, heading=_.LOGIN_ERROR_TITLE)
            return

        set_credentials(username=username, password=password)

    login_result = api.login()

    if login_result['result'] == False:
        query = "UPDATE `vars` SET `pswd`='', `last_login_success`='{last_login_success}' WHERE profile_id={profile_id}".format(last_login_success=0, profile_id=1)
        query_settings(query=query, return_result=False, return_insert=False, commit=True)

        if check_key(login_result['data'], 'error') and login_result['data']['error'] == 'toomany':
            gui.ok(message=_.TOO_MANY_DEVICES, heading=_.LOGIN_ERROR_TITLE)
        else:
            gui.ok(message=_.LOGIN_ERROR, heading=_.LOGIN_ERROR_TITLE)
    else:
        gui.ok(message=_.LOGIN_SUCCESS)

        query = "UPDATE `vars` SET `last_login_success`='{last_login_success}' WHERE profile_id={profile_id}".format(last_login_success=1, profile_id=1)
        query_settings(query=query, return_result=False, return_insert=False, commit=True)

    gui.refresh()

@plugin.route()
def live_tv(**kwargs):
    folder = plugin.Folder(title=_.LIVE_TV)

    for row in get_live_channels(addon=settings.getBool(key='enable_simple_iptv')):
        folder.add_item(
            label = row['label'],
            info = {'plot': row['description']},
            art = {'thumb': row['image']},
            path = row['path'],
            playable = row['playable'],
            context = row['context'],
        )

    return folder

@plugin.route()
def replaytv(**kwargs):
    folder = plugin.Folder(title=_.CHANNELS)

    folder.add_item(
        label = _.PROGSAZ,
        info = {'plot': _.PROGSAZDESC},
        path = plugin.url_for(func_or_url=replaytv_alphabetical),
    )

    for row in get_replay_channels():
        folder.add_item(
            label = row['label'],
            info = {'plot': row['description']},
            art = {'thumb': row['image']},
            path = row['path'],
            playable = row['playable'],
        )

    return folder

@plugin.route()
def replaytv_alphabetical(**kwargs):
    folder = plugin.Folder(title=_.PROGSAZ)
    label = _.OTHERTITLES

    folder.add_item(
        label = label,
        info = {'plot': _.OTHERTITLESDESC},
        path = plugin.url_for(func_or_url=replaytv_list, label=label, start=0, character='other'),
    )

    for character in string.ascii_uppercase:
        label = _.TITLESWITH + character

        folder.add_item(
            label = label,
            info = {'plot': _.TITLESWITHDESC + character},
            path = plugin.url_for(func_or_url=replaytv_list, label=label, start=0, character=character),
        )

    return folder

@plugin.route()
def replaytv_list(character, label='', start=0, **kwargs):
    start = int(start)
    folder = plugin.Folder(title=label)

    processed = process_replaytv_list(character=character, start=start)

    if check_key(processed, 'items'):
        folder.add_items(processed['items'])

    if check_key(processed, 'count') and check_key(processed, 'total') and processed['total'] > 50:
        folder.add_item(
            label = _(_.NEXT_PAGE, _bold=True),
            path = plugin.url_for(func_or_url=replaytv_list, character=character, label=label, start=start+processed['count']),
        )

    return folder

@plugin.route()
def replaytv_by_day(label='', image='', description='', station='', **kwargs):
    folder = plugin.Folder(title=label)

    for x in range(0, 7):
        curdate = datetime.date.today() - datetime.timedelta(days=x)

        itemlabel = ''

        if x == 0:
            itemlabel = _.TODAY + " - "
        elif x == 1:
            itemlabel = _.YESTERDAY + " - "

        if xbmc.getLanguage(xbmc.ISO_639_1) == 'nl':
            itemlabel += date_to_nl_dag(curdate=curdate) + curdate.strftime(" %d ") + date_to_nl_maand(curdate=curdate) + curdate.strftime(" %Y")
        else:
            itemlabel += curdate.strftime("%A %d %B %Y").capitalize()

        folder.add_item(
            label = itemlabel,
            info = {'plot': description},
            art = {'thumb': image},
            path = plugin.url_for(func_or_url=replaytv_content, label=itemlabel, day=x, station=station),
        )

    return folder

@plugin.route()
def replaytv_item(label=None, idtitle=None, start=0, **kwargs):
    start = int(start)
    folder = plugin.Folder(title=label)

    processed = process_replaytv_list_content(label=label, idtitle=idtitle, start=start)

    if check_key(processed, 'items'):
        folder.add_items(processed['items'])

    if check_key(processed, 'total') and check_key(processed, 'count') and int(processed['total']) > int(processed['count']):
        folder.add_item(
            label = _(_.NEXT_PAGE, _bold=True),
            path = plugin.url_for(func_or_url=replaytv_item, label=label, idtitle=idtitle, start=start+processed['count']),
        )

    return folder

@plugin.route()
def replaytv_content(label, day, station='', start=0, **kwargs):
    day = int(day)
    start = int(start)
    folder = plugin.Folder(title=label)

    processed = process_replaytv_content(station=station, day=day, start=start)

    if check_key(processed, 'items'):
        folder.add_items(processed['items'])

    if check_key(processed, 'total') and check_key(processed, 'count') and processed['total'] > processed['count']:
        folder.add_item(
            label = _(_.NEXT_PAGE, _bold=True),
            path = plugin.url_for(func_or_url=replaytv_content, label=label, day=day, station=station, start=processed['count']),
        )

    return folder

@plugin.route()
def vod(file, label, start=0, **kwargs):
    start = int(start)
    folder = plugin.Folder(title=label)

    processed = process_vod_content(data=file, start=start, type=label)

    if check_key(processed, 'items'):
        folder.add_items(processed['items'])

    if check_key(processed, 'total') and check_key(processed, 'count2') and processed['total'] > processed['count2']:
        folder.add_item(
            label = _(_.NEXT_PAGE, _bold=True),
            path = plugin.url_for(func_or_url=vod, file=file, label=label, start=processed['count2']),
        )

    return folder

@plugin.route()
def vod_series(label, description, image, id, **kwargs):
    folder = plugin.Folder(title=label)

    items = []

    seasons = api.vod_seasons(id)

    title = label

    for season in seasons:
        label = _.SEASON + " " + unicode(season['seriesNumber'])

        items.append(plugin.Item(
            label = label,
            info = {'plot': season['desc']},
            art = {
                'thumb': "{image_url}/vod/{image}/1920x1080.jpg?blurred=false".format(image_url=CONST_IMAGE_URL, image=season['image']),
                'fanart': "{image_url}/vod/{image}/1920x1080.jpg?blurred=false".format(image_url=CONST_IMAGE_URL, image=season['image'])
            },
            path = plugin.url_for(func_or_url=vod_season, label=label, title=title, id=season['id']),
        ))

    folder.add_items(items)

    return folder

@plugin.route()
def vod_season(label, title, id, **kwargs):
    folder = plugin.Folder(title=label)

    items = []

    season = api.vod_season(id)

    for episode in season:
        items.append(plugin.Item(
            label = episode['episodeNumber'] + " - " + episode['title'],
            info = {
                'plot': episode['desc'],
                'duration': episode['duration'],
                'mediatype': 'video',
            },
            art = {
                'thumb': "{image_url}/vod/{image}/1920x1080.jpg?blurred=false".format(image_url=CONST_IMAGE_URL, image=episode['image']),
                'fanart': "{image_url}/vod/{image}/1920x1080.jpg?blurred=false".format(image_url=CONST_IMAGE_URL, image=episode['image'])
            },
            path = plugin.url_for(func_or_url=play_video, type='vod', channel=None, id=episode['id'], title=title, _is_live=False),
            playable = True,
        ))

    folder.add_items(items)

    return folder

@plugin.route()
def search_menu(**kwargs):
    folder = plugin.Folder(title=_.SEARCHMENU)
    label = _.NEWSEARCH

    folder.add_item(
        label = label,
        info = {'plot': _.NEWSEARCHDESC},
        path = plugin.url_for(func_or_url=search),
    )

    profile_settings = load_profile(profile_id=1)

    for x in range(1, 10):
        searchstr = profile_settings['search' + unicode(x)]

        if searchstr != '':
            label = searchstr

            folder.add_item(
                label = label,
                info = {'plot': _(_.SEARCH_FOR, query=searchstr)},
                path = plugin.url_for(func_or_url=search, query=searchstr),
            )

    return folder

@plugin.route()
def search(query=None, **kwargs):
    items = []

    if not query:
        query = gui.input(message=_.SEARCH, default='').strip()

        if not query:
            return

        query = "UPDATE `vars` SET `search10`=`search9`, `search9`=`search8`, `search7`=`search6`, `search6`=`search5`, `search5`=`search4`, `search4`=`search3`, `search3`=`search2`, `search2`=`search1`, `search1`='{search1}' WHERE profile_id={profile_id}".format(search1=query, profile_id=1)
        query_settings(query=query, return_result=False, return_insert=False, commit=False)

    folder = plugin.Folder(title=_(_.SEARCH_FOR, query=query))

    processed = process_replaytv_search(search=query)
    items += processed['items']

    #if settings.getBool('showMoviesSeries'):
    #    processed = process_vod_content(data='series', start=0, search=query, type=_.SERIES)
    #    items += processed['items']
    #    processed = process_vod_content(data='movies', start=0, search=query, type=_.MOVIES)
    #    items += processed['items']
    #    processed = process_vod_content(data='kidsseries', start=0, search=query, type=_.KIDS_SERIES)
    #    items += processed['items']
    #    processed = process_vod_content(data='kidsmovies', start=0, search=query, type=_.KIDS_MOVIES)
    #    items += processed['items']

    items[:] = sorted(items, key=_sort_replay_items, reverse=True)
    items = items[:25]

    folder.add_items(items)

    return folder

@plugin.route()
def settings_menu(**kwargs):
    folder = plugin.Folder(title=_.SETTINGS)

    folder.add_item(label=_.CHANNEL_PICKER, path=plugin.url_for(func_or_url=channel_picker_menu))
    folder.add_item(label=_.SET_IPTV, path=plugin.url_for(func_or_url=plugin._set_settings_iptv))
    folder.add_item(label=_.SET_KODI, path=plugin.url_for(func_or_url=plugin._set_settings_kodi))
    folder.add_item(label=_.DOWNLOAD_SETTINGS, path=plugin.url_for(func_or_url=plugin._download_settings))
    folder.add_item(label=_.DOWNLOAD_EPG, path=plugin.url_for(func_or_url=plugin._download_epg))
    folder.add_item(label=_.INSTALL_WV_DRM, path=plugin.url_for(func_or_url=plugin._ia_install))
    folder.add_item(label=_.RESET_SESSION, path=plugin.url_for(func_or_url=login, ask=False))
    folder.add_item(label=_.RESET, path=plugin.url_for(func_or_url=reset_addon))
    folder.add_item(label=_.LOGOUT, path=plugin.url_for(func_or_url=logout))

    folder.add_item(label="Addon " + _.SETTINGS, path=plugin.url_for(func_or_url=plugin._settings))

    return folder

@plugin.route()
def channel_picker_menu(**kwargs):
    folder = plugin.Folder(title=_.CHANNEL_PICKER)

    folder.add_item(label=_.LIVE_TV, path=plugin.url_for(func_or_url=channel_picker, type='live'))
    folder.add_item(label=_.CHANNELS, path=plugin.url_for(func_or_url=channel_picker, type='replay'))
    folder.add_item(label=_.SIMPLEIPTV, path=plugin.url_for(func_or_url=channel_picker, type='epg'))

    return folder

@plugin.route()
def channel_picker(type, **kwargs):
    if type=='live':
        title = _.LIVE_TV
        rows = get_live_channels(addon=False, all=True)
    elif type=='replay':
        title = _.CHANNELS
        rows = get_replay_channels(all=True)
    else:
        title = _.SIMPLEIPTV
        rows = get_live_channels(addon=False, all=True)

    folder = plugin.Folder(title=title)
    prefs = load_prefs(profile_id=1)
    results = load_tests(profile_id=1)
    type = unicode(type)

    for row in rows:
        id = unicode(row['channel'])

        if not prefs or not check_key(prefs, id) or prefs[id][type] == 1:
            color = 'green'
        else:
            color = 'red'

        label = _(row['label'], _bold=True, _color=color)

        if results and check_key(results, id):
            if results[id][type] == 1:
                label += _(' (' + _.TEST_SUCCESS + ')', _bold=False, _color='green')
            else:
                label += _(' (' + _.TEST_FAILED + ')', _bold=False, _color='red')
        else:
            label += _(' (' + _.NOT_TESTED + ')', _bold=False, _color='orange')

        if not prefs or not check_key(prefs, id) or prefs[id][type + '_auto'] == 1:
            choice = _(' ,' + _.AUTO_CHOICE + '', _bold=False, _color='green')
        else:
            choice = _(' ,' + _.MANUAL_CHOICE + '', _bold=False, _color='orange')

        label += choice

        folder.add_item(
            label = label,
            art = {'thumb': row['image']},
            path = plugin.url_for(func_or_url=change_channel, type=type, id=id, change=False),
            context = [
                (_.AUTO_CHOICE_SET, 'Container.Update({context_url})'.format(context_url=plugin.url_for(func_or_url=change_channel, type=type, id=id, change=True)), ),
                #(_.TEST_CHANNEL, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=test_channel, channel=id)), ),
            ],
            playable = False,
        )

    return folder

@plugin.route()
def test_channel(channel, **kwargs):
    profile_settings = load_profile(profile_id=1)
    test_running = profile_settings['test_running']

    while not api._abortRequested and not xbmc.Monitor().abortRequested() and test_running == 1:
        query = "UPDATE `vars` SET `last_playing`='{last_playing}' WHERE profile_id={profile_id}".format(last_playing=int(time.time()), profile_id=1)
        query_settings(query=query, return_result=False, return_insert=False, commit=True)

        if xbmc.Monitor().waitForAbort(1):
            api._abortRequested = True
            break

        profile_settings = load_profile(profile_id=1)
        test_running = profile_settings['test_running']

    if api._abortRequested or xbmc.Monitor().abortRequested():
        return None

    query = "UPDATE `vars` SET `last_playing`=0 WHERE profile_id={profile_id}".format(profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)
    api.test_channels(tested=True, channel=channel)

@plugin.route()
def change_channel(type, id, change, **kwargs):
    if not id or len(unicode(id)) == 0 or not type or len(unicode(type)) == 0:
        return False

    prefs = load_prefs(profile_id=1)
    id = unicode(id)
    type = unicode(type)

    mod_pref = {
        'live': 1,
        'live_auto': 1,
        'replay': 1,
        'replay_auto': 1,
        'epg': 1,
        'epg_auto': 1,
    }

    if change == 'False':
        mod_pref[unicode(type) + '_auto'] = 0

        if not check_key(prefs, id):
            mod_pref[type] = 0
        else:
            if prefs[id][type] == 1:
                mod_pref[type] = 0
            else:
                mod_pref[type] = 1
    else:
        mod_pref[unicode(type) + '_auto'] = 1

        results = load_tests(profile_id=1)

        if not results or not check_key(results, id) or not results[id][type] == 1:
            mod_pref[type] = 1
        else:
            mod_pref[type] = 0

    query = "REPLACE INTO `prefs_{profile_id}` VALUES ('{id}', '{live}', '{live_auto}', '{replay}', '{replay_auto}', '{epg}', '{epg_auto}')".format(profile_id=1, id=id, live=mod_pref['live'], live_auto=mod_pref['live_auto'], replay=mod_pref['replay'], replay_auto=mod_pref['replay_auto'], epg=mod_pref['epg'], epg_auto=mod_pref['epg_auto'])
    query_settings(query=query, return_result=False, return_insert=False, commit=True)

    if type == 'epg':
        create_playlist()

    xbmc.executeJSONRPC('{{"jsonrpc":"2.0","id":1,"method":"GUI.ActivateWindow","params":{{"window":"videos","parameters":["plugin://' + unicode(ADDON_ID) + '/?_=channel_picker&type=' + type + '"]}}}}')

@plugin.route()
def reset_addon(**kwargs):
    plugin._reset()
    logout()

@plugin.route()
def logout(**kwargs):
    if not gui.yes_no(message=_.LOGOUT_YES_NO):
        return

    query = "UPDATE `vars` SET `pswd`='', `username`='' WHERE profile_id={profile_id}".format(profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)
    gui.refresh()

@plugin.route()
def play_video(type=None, channel=None, id=None, title=None, from_beginning='False', **kwargs):
    profile_settings = load_profile(profile_id=1)

    properties = {}

    if not type and not len(unicode(type)) > 0:
        return False

    if type == 'program':
        properties['seekTime'] = 1

    playdata = api.play_url(type=type, channel=channel, id=id, from_beginning=from_beginning)

    if not playdata or not check_key(playdata, 'path'):
        return False

    CDMHEADERS = CONST_BASE_HEADERS
    CDMHEADERS['User-Agent'] = _user_agent

    if check_key(playdata, 'license'):
        item_inputstream = inputstream.Widevine(
            license_key = playdata['license'],
        )
    else:
        item_inputstream = inputstream.MPD()

    itemlabel = ''
    label2 = ''
    description = ''
    program_image = ''
    program_image_large = ''
    duration = 0
    cast = []
    director = []
    writer = []
    genres = []

    if playdata['info']:
        if check_key(playdata['info'], 'params'):
            if check_key(playdata['info']['params'], 'start') and check_key(playdata['info']['params'], 'end'):
                startT = datetime.datetime.fromtimestamp(time.mktime(time.strptime(playdata['info']['params']['start'], "%Y-%m-%dT%H:%M:%SZ")))
                endT = datetime.datetime.fromtimestamp(time.mktime(time.strptime(playdata['info']['params']['end'], "%Y-%m-%dT%H:%M:%SZ")))

                duration = int((endT - startT).total_seconds())

                if xbmc.getLanguage(xbmc.ISO_639_1) == 'nl':
                    itemlabel = '{weekday} {day} {month} {yearhourminute} '.format(weekday=date_to_nl_dag(startT), day=startT.strftime("%d"), month=date_to_nl_maand(startT), yearhourminute=startT.strftime("%Y %H:%M"))
                else:
                    itemlabel = startT.strftime("%A %d %B %Y %H:%M ").capitalize()

                itemlabel += " - "

        if title:
            itemlabel += title + ' - '

        if check_key(playdata['info'], 'title'):
            itemlabel += playdata['info']['title']

        if check_key(playdata['info'], 'desc'):
            description = playdata['info']['desc']

        if check_key(playdata['info'], 'images') and check_key(playdata['info']['images'][0], 'url'):
            program_image = playdata['info']['images'][0]['url']
            program_image_large = playdata['info']['images'][0]['url']

        if check_key(playdata['info'], 'params'):
            if check_key(playdata['info']['params'], 'credits'):
                for castmember in playdata['info']['params']['credits']:
                    if castmember['role'] == "Actor":
                        cast.append(castmember['person'])
                    elif castmember['role'] == "Director":
                        director.append(castmember['person'])
                    elif castmember['role'] == "Writer":
                        writer.append(castmember['person'])

            if check_key(playdata['info']['params'], 'genres'):
                for genre in playdata['info']['params']['genres']:
                    genres.append(genre['title'])

            if check_key(playdata['info']['params'], 'duration'):
                duration = playdata['info']['params']['duration']

            epcode = ''

            if check_key(playdata['info']['params'], 'seriesSeason'):
                epcode += 'S' + unicode(playdata['info']['params']['seriesSeason'])

            if check_key(playdata['info']['params'], 'seriesEpisode'):
                epcode += 'E' + unicode(playdata['info']['params']['seriesEpisode'])

            if check_key(playdata['info']['params'], 'episodeTitle'):
                label2 = playdata['info']['params']['episodeTitle']

                if len(epcode) > 0:
                    label2 += " (" + epcode + ")"
            elif check_key(playdata['info'], 'title'):
                label2 = playdata['info']['title']

            if check_key(playdata['info']['params'], 'channelId'):
                rows = load_file(file='channels.json', isJSON=True)

                if rows:
                    for row in rows:
                        channeldata = api.get_channel_data(row=row)

                        if channeldata['channel_id'] == playdata['info']['params']['channelId']:
                            label2 += " - "  + channeldata['label']
                            break

    settings.setInt(key='_stream_duration', value=duration)

    listitem = plugin.Item(
        label = itemlabel,
        label2 = label2,
        art = {
            'thumb': program_image,
            'fanart': program_image_large
        },
        info = {
            'cast': cast,
            'writer': writer,
            'director': director,
            'genre': genres,
            'plot': description,
            'duration': duration,
            'mediatype': 'video',
        },
        properties = properties,
        path = playdata['path'],
        headers = CDMHEADERS,
        inputstream = item_inputstream,
    )

    return listitem

@plugin.route()
def switchChannel(channel_uid, **kwargs):
    global backend

    play_url = 'PlayMedia(pvr://channels/tv/{allchan}/{backend}_{channel_uid}.pvr)'.format(allchan=xbmc.getLocalizedString(19287), backend=backend, channel_uid=channel_uid)
    xbmc.executebuiltin(play_url)

#Support functions
def first_boot():
    if gui.yes_no(message=_.SET_IPTV):
        try:
            plugin._set_settings_iptv()
        except:
            pass
    if gui.yes_no(message=_.SET_KODI):
        try:
            plugin._set_settings_kodi()
        except:
            pass

    query = "UPDATE `vars` SET `first_boot`='{first_boot}' WHERE profile_id={profile_id}".format(first_boot=0, profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)

def get_live_channels(addon=False, all=False):
    global backend
    channels = []
    pvrchannels = []

    query = "SELECT * FROM `channels`"
    data = query_epg(query=query, return_result=True, return_insert=False, commit=False)

    prefs = load_prefs(profile_id=1)

    if data:
        if addon:
            query_addons = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddons", "params": {"type": "xbmc.pvrclient"}}'))

            if check_key(query_addons, 'result') and check_key(query_addons['result'], 'addons'):
                addons = query_addons['result']['addons']
                backend = addons[0]['addonid']

                query_channel = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "PVR.GetChannels", "params": {"channelgroupid": "alltv", "properties" :["uniqueid"]},"id": 1}'))

                if check_key(query_channel, 'result') and check_key(query_channel['result'], 'channels'):
                    pvrchannels = query_channel['result']['channels']

        for row in data:
            path = plugin.url_for(func_or_url=play_video, type='channel', channel=row['id'], id=row['id'], _is_live=True)
            playable = True

            for channel in pvrchannels:
                if channel['label'] == row['name']:
                    channel_uid = channel['uniqueid']
                    path = plugin.url_for(func_or_url=switchChannel, channel_uid=channel_uid)
                    playable = False
                    break


            if '18+' in row['name']:
                continue

            id = unicode(row['id'])

            if all or not prefs or not check_key(prefs, id) or prefs[id]['live'] == 1:
                image_path = ADDON_PROFILE + "images" + os.sep + unicode(row['id']) + ".png"

                if os.path.isfile(image_path):
                    image = image_path
                else:
                    image = row['icon']

                channels.append({
                    'label': row['name'],
                    'channel': row['id'],
                    'chno': row['channelno'],
                    'description': row['description'],
                    'image': image,
                    'path':  path,
                    'playable': playable,
                    'context': [
                        (_.START_BEGINNING, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=play_video, type='channel', channel=row['id'], id=row['assetid'], from_beginning=True)), ),
                    ],
                })

        channels[:] = sorted(channels, key=_sort_live)

    return channels

def get_replay_channels(all=False):
    channels = []

    query = "SELECT * FROM `channels`"
    data = query_epg(query=query, return_result=True, return_insert=False, commit=False)

    prefs = load_prefs(profile_id=1)

    if data:
        for row in data:
            if '18+' in row['name']:
                continue

            id = unicode(row['id'])

            if all or not prefs or not check_key(prefs, id) or prefs[id]['replay'] == 1:
                image_path = ADDON_PROFILE + "images" + os.sep + unicode(row['id']) + ".png"

                if os.path.isfile(image_path):
                    image = image_path
                else:
                    image = row['icon']

                channels.append({
                    'label': row['name'],
                    'channel': row['id'],
                    'chno': row['channelno'],
                    'description': row['description'],
                    'image': image,
                    'path': plugin.url_for(func_or_url=replaytv_by_day, image=row['icon'], description=row['description'], label=row['name'], station=row['id']),
                    'playable': False,
                    'context': [],
                })

        channels[:] = sorted(channels, key=_sort_live)

    return channels

def process_replaytv_list(character, start=0):
    profile_settings = load_profile(profile_id=1)

    now = datetime.datetime.now(pytz.timezone("Europe/Amsterdam"))
    sevendays = datetime.datetime.now(pytz.timezone("Europe/Amsterdam")) - datetime.timedelta(days=7)
    nowstamp = int((now - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds())
    sevendaysstamp = int((sevendays - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds())

    prefs = load_prefs(profile_id=1)
    channels_ar = []

    if prefs:
        for row in prefs:
            currow = prefs[row]

            if currow['replay'] == 1:
                channels_ar.append(row)

    channels = "', '".join(map(str, channels_ar))

    query = "SELECT idtitle, title, icon FROM `epg` WHERE first='{first}' AND start < {nowstamp} AND end > {sevendaysstamp} AND channel IN ('{channels}') GROUP BY idtitle LIMIT 51 OFFSET {start}".format(first=character, nowstamp=nowstamp, sevendaysstamp=sevendaysstamp, channels=channels, start=start)
    data = query_epg(query=query, return_result=True, return_insert=False, commit=False)

    start = int(start)
    items = []
    item_count = 0

    if not data:
        return {'items': items, 'count': item_count, 'total': 0}

    for row in data:
        if item_count == 51:
            break

        item_count += 1

        label = row['title']
        idtitle = row['idtitle']

        items.append(plugin.Item(
            label = label,
            art = {
                'thumb': row['icon'].replace(profile_settings['img_size'], '1920x1080'),
                'fanart': row['icon'].replace(profile_settings['img_size'], '1920x1080')
            },
            path = plugin.url_for(func_or_url=replaytv_item, label=label, idtitle=idtitle, start=0),
        ))

    returnar = {'items': items, 'count': item_count, 'total': len(data)}

    return returnar

def process_replaytv_search(search):
    profile_settings = load_profile(profile_id=1)

    now = datetime.datetime.now(pytz.timezone("Europe/Amsterdam"))
    sevendays = datetime.datetime.now(pytz.timezone("Europe/Amsterdam")) - datetime.timedelta(days=7)
    nowstamp = int((now - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds())
    sevendaysstamp = int((sevendays - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds())

    prefs = load_prefs(profile_id=1)
    channels_ar = []

    if prefs:
        for row in prefs:
            currow = prefs[row]

            if currow['replay'] == 1:
                channels_ar.append(row)

    channels = "', '".join(map(str, channels_ar))

    query = "SELECT idtitle, title, icon FROM `epg` WHERE start < {nowstamp} AND end > {sevendaysstamp} AND channel IN ('{channels}') GROUP BY idtitle".format(nowstamp=nowstamp, sevendaysstamp=sevendaysstamp, channels=channels)
    data = query_epg(query=query, return_result=True, return_insert=False, commit=False)

    items = []

    if not data:
        return {'items': items}

    for row in data:
        fuzz_set = fuzz.token_set_ratio(row['title'], search)
        fuzz_partial = fuzz.partial_ratio(row['title'], search)
        fuzz_sort = fuzz.token_sort_ratio(row['title'], search)

        if (fuzz_set + fuzz_partial + fuzz_sort) > 160:
            label = row['title'] + ' (ReplayTV)'
            idtitle = row['idtitle']

            items.append(plugin.Item(
                label = label,
                art = {
                    'thumb': row['icon'].replace(profile_settings['img_size'], '1920x1080'),
                    'fanart': row['icon'].replace(profile_settings['img_size'], '1920x1080')
                },
                properties = {"fuzz_set": fuzz_set, "fuzz_sort": fuzz_sort, "fuzz_partial": fuzz_partial, "fuzz_total": fuzz_set + fuzz_partial + fuzz_sort},
                path = plugin.url_for(func_or_url=replaytv_item, label=label, idtitle=idtitle, start=0),
            ))

    returnar = {'items': items}

    return returnar

def process_replaytv_content(station, day=0, start=0):
    profile_settings = load_profile(profile_id=1)

    day = int(day)
    start = int(start)
    curdate = datetime.date.today() - datetime.timedelta(days=day)

    startDate = convert_datetime_timezone(datetime.datetime(curdate.year, curdate.month, curdate.day, 0, 0, 0), "Europe/Amsterdam", "UTC")
    endDate = convert_datetime_timezone(datetime.datetime(curdate.year, curdate.month, curdate.day, 23, 59, 59), "Europe/Amsterdam", "UTC")
    startTimeStamp = int((startDate - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds())
    endTimeStamp = int((endDate - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds())

    query = "SELECT * FROM `epg` WHERE channel='{channel}' AND start >= {startTime} AND start <= {endTime} LIMIT 51 OFFSET {start}".format(channel=station, startTime=startTimeStamp, endTime=endTimeStamp, start=start)
    data = query_epg(query=query, return_result=True, return_insert=False, commit=False)

    items = []
    item_count = 0

    if not data:
        return {'items': items, 'count': item_count, 'total': 0}

    for row in data:
        if item_count == 51:
            break

        item_count += 1

        startT = datetime.datetime.fromtimestamp(row['start'])
        startT = convert_datetime_timezone(startT, "Europe/Amsterdam", "Europe/Amsterdam")
        endT = datetime.datetime.fromtimestamp(row['end'])
        endT = convert_datetime_timezone(endT, "Europe/Amsterdam", "Europe/Amsterdam")

        if endT < (datetime.datetime.now(pytz.timezone("Europe/Amsterdam")) - datetime.timedelta(days=7)):
            continue

        label = startT.strftime("%H:%M") + " - " + row['title']

        description = row['description']

        duration = int((endT - startT).total_seconds())

        program_image = row['icon'].replace(profile_settings['img_size'], '1920x1080')
        program_image_large = row['icon'].replace(profile_settings['img_size'], '1920x1080')

        items.append(plugin.Item(
            label = label,
            info = {
                'plot': description,
                'duration': duration,
                'mediatype': 'video',
            },
            art = {
                'thumb': program_image,
                'fanart': program_image_large
            },
            path = plugin.url_for(func_or_url=play_video, type='program', channel=row['channel'], id=row['program_id'], duration=duration, _is_live=False),
            playable = True,
        ))

    returnar = {'items': items, 'count': item_count, 'total': len(data)}

    return returnar

def process_replaytv_list_content(label, idtitle, start=0):
    profile_settings = load_profile(profile_id=1)

    start = int(start)

    now = datetime.datetime.now(pytz.timezone("Europe/Amsterdam"))
    sevendays = datetime.datetime.now(pytz.timezone("Europe/Amsterdam")) - datetime.timedelta(days=7)
    nowstamp = int((now - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds())
    sevendaysstamp = int((sevendays - datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)).total_seconds())

    prefs = load_prefs(profile_id=1)
    channels_ar = []

    if prefs:
        for row in prefs:
            currow = prefs[row]

            if currow['replay'] == 1:
                channels_ar.append(row)

    channels = "', '".join(map(str, channels_ar))

    query = "SELECT * FROM `channels`"
    data = query_epg(query=query, return_result=True, return_insert=False, commit=False)

    channels_ar2 = {}

    if data:
        for row in data:
            channels_ar2[unicode(row['id'])] = row['name']

    query = "SELECT * FROM `epg` WHERE idtitle='{idtitle}' AND start < {nowstamp} AND end > {sevendaysstamp} AND channel IN ('{channels}') LIMIT 51 OFFSET {start}".format(idtitle=idtitle, nowstamp=nowstamp, sevendaysstamp=sevendaysstamp, channels=channels, start=start)
    data = query_epg(query=query, return_result=True, return_insert=False, commit=False)

    items = []
    item_count = 0

    if not data:
        return {'items': items, 'count': item_count, 'total': 0}

    for row in data:
        if item_count == 51:
            break

        item_count += 1

        startT = datetime.datetime.fromtimestamp(row['start'])
        startT = convert_datetime_timezone(startT, "Europe/Amsterdam", "Europe/Amsterdam")
        endT = datetime.datetime.fromtimestamp(row['end'])
        endT = convert_datetime_timezone(endT, "Europe/Amsterdam", "Europe/Amsterdam")

        if xbmc.getLanguage(xbmc.ISO_639_1) == 'nl':
            itemlabel = '{weekday} {day} {month} {yearhourminute} '.format(weekday=date_to_nl_dag(startT), day=startT.strftime("%d"), month=date_to_nl_maand(startT), yearhourminute=startT.strftime("%Y %H:%M"))
        else:
            itemlabel = startT.strftime("%A %d %B %Y %H:%M ").capitalize()

        itemlabel += row['title'] + " (" + channels_ar2[unicode(row['channel'])] + ")"

        description = row['description']
        duration = int((endT - startT).total_seconds())
        program_image = row['icon'].replace(profile_settings['img_size'], '1920x1080')
        program_image_large = row['icon'].replace(profile_settings['img_size'], '1920x1080')

        items.append(plugin.Item(
            label = itemlabel,
            info = {
                'plot': description,
                'duration': duration,
                'mediatype': 'video',
            },
            art = {
                'thumb': program_image,
                'fanart': program_image_large
            },
            path = plugin.url_for(func_or_url=play_video, type='program', channel=row['channel'], id=row['program_id'], duration=duration, _is_live=False),
            playable = True,
        ))

    returnar = {'items': items, 'count': item_count, 'total': len(data)}

    return returnar

def process_vod_content(data, start=0, search=None, type=None):
    profile_settings = load_profile(profile_id=1)

    subscription = load_file(file='vod_subscription.json', isJSON=True)

    start = int(start)

    items = []
    count = start
    item_count = 0

    if sys.version_info >= (3, 0):
        subscription = list(subscription)

    query = "SELECT * FROM `{table}` ORDER BY title ASC LIMIT 999999 OFFSET {start}".format(table=data, start=start)
    data = query_epg(query=query, return_result=True, return_insert=False, commit=False)

    if not data:
        return {'items': items, 'count': item_count, 'count2': count, 'total': 0}

    for row in data:
        if item_count == 50:
            break

        count += 1

        id = row['id']
        label = row['title']

        if not int(id) in subscription:
            continue

        if search:
            fuzz_set = fuzz.token_set_ratio(label,search)
            fuzz_partial = fuzz.partial_ratio(label,search)
            fuzz_sort = fuzz.token_sort_ratio(label,search)

            if (fuzz_set + fuzz_partial + fuzz_sort) > 160:
                properties = {"fuzz_set": fuzz.token_set_ratio(label,search), "fuzz_sort": fuzz.token_sort_ratio(label,search), "fuzz_partial": fuzz.partial_ratio(label,search), "fuzz_total": fuzz.token_set_ratio(label,search) + fuzz.partial_ratio(label,search) + fuzz.token_sort_ratio(label,search)}
                label = label + " (" + type + ")"
            else:
                continue

        item_count += 1

        properties = []
        description = row['description']
        duration = int(row['duration'])
        program_image = row['icon'].replace(profile_settings['img_size'], '1920x1080')
        program_image_large = row['icon'].replace(profile_settings['img_size'], '1920x1080')

        if row['type'] == "show":
            path = plugin.url_for(func_or_url=vod_series, label=label, description=description, image=program_image_large, id=id)
            info = {'plot': description}
            playable = False
        else:
            path = plugin.url_for(func_or_url=play_video, type='vod', channel=None, id=id, duration=duration, _is_live=False)
            info = {'plot': description, 'duration': duration, 'mediatype': 'video'}
            playable = True

        items.append(plugin.Item(
            label = label,
            properties = properties,
            info = info,
            art = {
                'thumb': program_image,
                'fanart': program_image_large
            },
            path = path,
            playable = playable,
        ))

    if item_count == 50:
        total = int(len(data) + count)
    else:
        total = count

    returnar = {'items': items, 'count': item_count, 'count2': count, 'total': total}

    return returnar

def _sort_live(element):
    return element['chno']

def _sort_replay_items(element):
    return element.get_li().getProperty('fuzz_total')