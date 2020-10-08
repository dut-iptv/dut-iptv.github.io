import _strptime

import datetime, json, pytz, re, string, sys, time, xbmc

from fuzzywuzzy import fuzz
from resources.lib.api import API
from resources.lib.base import plugin, gui, signals, inputstream, settings
from resources.lib.base.constants import ADDON_ID
from resources.lib.base.exceptions import Error
from resources.lib.base.log import log
from resources.lib.base.util import check_key, convert_datetime_timezone, date_to_nl_dag, date_to_nl_maand, get_credentials, load_file, write_file
from resources.lib.constants import CONST_IMAGE_URL
from resources.lib.language import _

try:
    unicode
except NameError:
    unicode = str

ADDON_HANDLE = int(sys.argv[1])
api = API()
backend = ''
query_channel = {}

_debug_mode = settings.getBool(key='enable_debug')
_first_boot = settings.getBool(key='_first_boot')
_user_agent = settings.get(key='_user_agent')

@plugin.route('')
def home(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.home')

    if _first_boot:
        first_boot()

    folder = plugin.Folder()

    if _debug_mode:
        log.debug('plugin.logged_in: {logged_in}'.format(logged_in=plugin.logged_in))

    if not plugin.logged_in:
        folder.add_item(label=_(_.LOGIN, _bold=True), path=plugin.url_for(func_or_url=login))
    else:
        folder.add_item(label=_(_.LIVE_TV, _bold=True),  path=plugin.url_for(func_or_url=live_tv))
        folder.add_item(label=_(_.CHANNELS, _bold=True), path=plugin.url_for(func_or_url=replaytv))
        folder.add_item(label=_(_.SERIES, _bold=True), path=plugin.url_for(func_or_url=list_alphabetical, type='series'))
        folder.add_item(label=_(_.RECOMMENDED, _bold=True), path=plugin.url_for(func_or_url=vod, file='tipfeed', label=_.RECOMMENDED, start=0))
        folder.add_item(label=_(_.WATCHAHEAD, _bold=True), path=plugin.url_for(func_or_url=vod, file='watchahead', label=_.WATCHAHEAD, start=0))
        folder.add_item(label=_(_.MOVIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='movies', label=_.MOVIES, start=0))
        folder.add_item(label=_(_.SERIESBINGE, _bold=True), path=plugin.url_for(func_or_url=vod, file='seriesbinge', label=_.SERIESBINGE, start=0))
        folder.add_item(label=_(_.MOSTVIEWED, _bold=True), path=plugin.url_for(func_or_url=vod, file='mostviewed', label=_.MOSTVIEWED, start=0))
        folder.add_item(label=_(_.SEARCH, _bold=True), path=plugin.url_for(func_or_url=search_menu))

    folder.add_item(label=_.SETTINGS, path=plugin.url_for(func_or_url=settings_menu))

    if _debug_mode:
        log.debug('Execution Done: plugin.home')

    return folder

#Main menu items
@plugin.route()
def login(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.login')

    creds = get_credentials()
    username = gui.input(message=_.ASK_USERNAME, default=creds['username']).strip()

    if not len(username) > 0:
        gui.ok(message=_.EMPTY_USER, heading=_.LOGIN_ERROR_TITLE)

        if _debug_mode:
            log.debug('Username length = 0')
            log.debug('Execution Done: plugin.login')

        return

    password = gui.input(message=_.ASK_PASSWORD, hide_input=True).strip()

    if not len(password) > 0:
        gui.ok(message=_.EMPTY_PASS, heading=_.LOGIN_ERROR_TITLE)

        if _debug_mode:
            log.debug('Password length = 0')
            log.debug('Execution Done: plugin.login')

        return

    api.login(username=username, password=password, channels=True)
    plugin.logged_in = api.logged_in

    if _debug_mode:
        log.debug('plugin.logged_in: {logged_in}'.format(logged_in=plugin.logged_in))

    gui.refresh()

    if _debug_mode:
        log.debug('Execution Done: plugin.login')

@plugin.route()
def live_tv(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.live_tv')
        log.debug('Settings Enable Simple IPTV: {simpleiptv}'.format(simpleiptv=settings.getBool(key='enable_simple_iptv')))

    folder = plugin.Folder(title=_.LIVE_TV)
    prefs = load_file(file="channel_prefs.json", isJSON=True)

    for row in get_live_channels(addon=settings.getBool(key='enable_simple_iptv')):
        id = unicode(row['channel'])

        if not prefs or not check_key(prefs, id) or prefs[id]['live'] == 'true':
            folder.add_item(
                label = row['label'],
                info = {'plot': row['description']},
                art = {'thumb': row['image']},
                path = row['path'],
                playable = row['playable'],
                context = row['context'],
            )

    if _debug_mode:
        log.debug('Execution Done: plugin.live_tv')

    return folder

@plugin.route()
def replaytv(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.replaytv')

    folder = plugin.Folder(title=_.CHANNELS)
    prefs = load_file(file="channel_prefs.json", isJSON=True)

    folder.add_item(
        label = _.PROGSAZ,
        info = {'plot': _.PROGSAZDESC},
        path = plugin.url_for(func_or_url=replaytv_alphabetical),
    )

    for row in get_replay_channels():
        id = unicode(row['channel'])

        if not prefs or not check_key(prefs, id) or prefs[id]['replay'] == 'true':
            folder.add_item(
                label = row['label'],
                info = {'plot': row['description']},
                art = {'thumb': row['image']},
                path = row['path'],
                playable = row['playable'],
            )

    if _debug_mode:
        log.debug('Execution Done: plugin.replaytv')

    return folder

@plugin.route()
def list_alphabetical(type, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.list_alphabetical')
        log.debug('Vars: type={type}'.format(type=type))

    folder = plugin.Folder(title=_.PROGSAZ)
    label = _.OTHERTITLES

    if type == 'replaytv':
        path = plugin.url_for(func_or_url=replaytv_list, label=label, start=0, character='other')
    else:
        path = plugin.url_for(func_or_url=vod, file='series', label=_.SERIES, start=0, character='other')

    folder.add_item(
        label = label,
        info = {'plot': _.OTHERTITLESDESC},
        path = path,
    )

    for character in string.ascii_uppercase:
        label = _.TITLESWITH + character

        if type == 'replaytv':
            path = plugin.url_for(func_or_url=replaytv_list, label=label, start=0, character=character)
        else:
            path = plugin.url_for(func_or_url=vod, file='series', label=_.SERIES, start=0, character=character)

        folder.add_item(
            label = label,
            info = {'plot': _.TITLESWITHDESC + character},
            path = path,
        )

    if _debug_mode:
        log.debug('Execution Done: plugin.list_alphabetical')

    return folder

@plugin.route()
def replaytv_list(character, label='', start=0, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.replaytv_list')
        log.debug('Vars: character={character}, label={label}, start={start}'.format(character=character, label=label, start=start))

    start = int(start)
    folder = plugin.Folder(title=label)

    data = load_file(file='list_replay.json', isJSON=True)

    if not data:
        gui.ok(message=_.NO_REPLAY_TV_INFO, heading=_.NO_REPLAY_TV_INFO)
        return folder

    if not check_key(data, character):
        return folder

    processed = process_replaytv_list(data=data[character], start=start)

    if check_key(processed, 'items'):
        folder.add_items(processed['items'])

    if check_key(processed, 'count') and len(data[character]) > processed['count']:
        folder.add_item(
            label = _(_.NEXT_PAGE, _bold=True),
            path = plugin.url_for(func_or_url=replaytv_list, character=character, label=label, start=processed['count']),
        )

    if _debug_mode:
        log.debug('Execution Done: plugin.replaytv_list')

    return folder

@plugin.route()
def replaytv_by_day(label='', image='', description='', station='', **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.replaytv_by_day')
        log.debug('Vars: label={label}, image={image}, description={description}, station={station}'.format(label=label, image=image, description=description, station=station))

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

    if _debug_mode:
        log.debug('Execution Done: plugin.replaytv_by_day')

    return folder

@plugin.route()
def replaytv_item(ids=None, label=None, start=0, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.replaytv_item')
        log.debug('Vars: ids={ids}, label={label}, start={start}'.format(ids=ids, label=label, start=start))

    start = int(start)
    first = label[0]

    folder = plugin.Folder(title=label)

    if first.isalpha():
        data = load_file(file=first + "_replay.json", isJSON=True)
    else:
        data = load_file(file='other_replay.json', isJSON=True)

    if not data:
        return folder

    processed = process_replaytv_list_content(data=data, ids=ids, start=start)

    if check_key(processed, 'items'):
        folder.add_items(processed['items'])

    if check_key(processed, 'totalrows') and check_key(processed, 'count') and processed['totalrows'] > processed['count']:
        folder.add_item(
            label = _(_.NEXT_PAGE, _bold=True),
            path = plugin.url_for(func_or_url=replaytv_item, ids=ids, label=label, start=processed['count']),
        )

    if _debug_mode:
        log.debug('Execution Done: plugin.replaytv_item')

    return folder

@plugin.route()
def replaytv_content(label, day, station='', start=0, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.replaytv_content')
        log.debug('Vars: label={label}, day={day}, station={station}, start={start}'.format(label=label, day=day, station=station, start=start))

    day = int(day)
    start = int(start)
    folder = plugin.Folder(title=label)

    data = load_file(file=station + "_replay.json", isJSON=True)

    if not data:
        return folder

    totalrows = len(data)
    processed = process_replaytv_content(data=data, day=day, start=start)

    if check_key(processed, 'items'):
        folder.add_items(processed['items'])

    if check_key(processed, 'count') and totalrows > processed['count']:
        folder.add_item(
            label = _(_.NEXT_PAGE, _bold=True),
            path = plugin.url_for(func_or_url=replaytv_content, label=label, day=day, station=station, start=processed['count']),
        )

    if _debug_mode:
        log.debug('Execution Done: plugin.replaytv_content')

    return folder

@plugin.route()
def vod(file, label, start=0, character=None, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.vod')
        log.debug('Vars: file={file}, label={label}, start={start}, character={character}'.format(file=file, label=label, start=start, character=character))

    start = int(start)
    folder = plugin.Folder(title=label)

    if file != 'series':
        data = api.vod_download(type=file)
    else:
        data = load_file(file='vod.json', isJSON=True)[file]

    if not data:
        return folder

    processed = process_vod_content(data=data, start=start, type=label, character=character)

    if check_key(processed, 'items'):
        folder.add_items(processed['items'])

    if check_key(processed, 'count') and len(data) > processed['count']:
        folder.add_item(
            label = _(_.NEXT_PAGE, _bold=True),
            path = plugin.url_for(func_or_url=vod, file=file, label=label, start=processed['count'], character=character),
        )

    if _debug_mode:
        log.debug('Execution Done: plugin.vod')

    return folder

@plugin.route()
def vod_series(label, description, image, id, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.vod_series')
        log.debug('Vars: label={label}, description={description}, image={image}, id={id}'.format(label=label, description=description, image=image, id=id))

    folder = plugin.Folder(title=label)

    items = []

    seasons = api.vod_seasons(id)

    title = label

    if seasons and check_key(seasons, 'seasons'):
        if seasons['type'] == "seasons":
            seasons['seasons'][:] = sorted(seasons['seasons'], key=_sort_season)

            for season in seasons['seasons']:
                label = _.SEASON + " " + unicode(season['seriesNumber'].replace('Seizoen ', ''))

                if not 'http' in season['image']:
                    image_split = season['image'].rsplit('/', 1)

                    if len(image_split) == 2:
                        season['image'] = '{image_url}/thumbnails/hd1080/{image}'.format(image_url=CONST_IMAGE_URL, image=season['image'].rsplit('/', 1)[1])
                    else:
                        season['image'] = '{image_url}/{image}'.format(image_url=CONST_IMAGE_URL, image=season['image'])

                items.append(plugin.Item(
                    label = label,
                    info = {'plot': season['desc']},
                    art = {
                        'thumb': season['image'],
                        'fanart': season['image']
                    },
                    path = plugin.url_for(func_or_url=vod_season, label=label, title=title, series=id, id=season['id']),
                ))
        else:
            seasons['seasons'][:] = sorted(seasons['seasons'], key=_sort_episodes)

            for episode in seasons['seasons']:
                label = ''
                duration = 0

                if check_key(episode, 'seasonNumber'):
                    label += unicode(episode['seasonNumber'])

                if check_key(episode, 'episodeNumber'):
                    if len(label) > 0:
                        label += "."

                    label += unicode(episode['episodeNumber'])

                if check_key(episode, 'title'):
                    if len(label) > 0:
                        label += " - "

                    label += episode['title']

                if not 'http' in episode['image']:
                    image_split = episode['image'].rsplit('/', 1)

                    if len(image_split) == 2:
                        episode['image'] = '{image_url}/thumbnails/hd1080/{image}'.format(image_url=CONST_IMAGE_URL, image=episode['image'].rsplit('/', 1)[1])
                    else:
                        episode['image'] = '{image_url}/{image}'.format(image_url=CONST_IMAGE_URL, image=episode['image'])

                if check_key(episode, 'duration'):
                    duration = episode['duration']

                items.append(plugin.Item(
                    label = label,
                    info = {
                        'plot': episode['desc'],
                        'duration': duration,
                        'mediatype': 'video',
                    },
                    art = {
                        'thumb': episode['image'],
                        'fanart': episode['image']
                    },
                    path = plugin.url_for(func_or_url=play_video, type='vod', channel=None, id=episode['id'], _is_live=False),
                    playable = True,
                ))

        folder.add_items(items)

    if _debug_mode:
        log.debug('Execution Done: plugin.vod_series')

    return folder

@plugin.route()
def vod_season(label, title, series, id, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.vod_season')
        log.debug('Vars: label={label}, title={title}, series={series}, id={id}'.format(label=label, title=title, series=series, id=id))

    folder = plugin.Folder(title=label)

    items = []

    season = api.vod_season(series=series, id=id)

    season[:] = sorted(season, key=_sort_episodes)

    for episode in season:
        label = ''

        if check_key(episode, 'start'):
            startT = datetime.datetime.fromtimestamp(time.mktime(time.strptime(episode['start'], "%Y-%m-%dT%H:%M:%S")))
            startT = convert_datetime_timezone(startT, "UTC", "UTC")

            if xbmc.getLanguage(xbmc.ISO_639_1) == 'nl':
                label += '{weekday} {day} {month} {yearhourminute} '.format(weekday=date_to_nl_dag(startT), day=startT.strftime("%d"), month=date_to_nl_maand(startT), yearhourminute=startT.strftime("%Y %H:%M"))
            else:
                label += startT.strftime("%A %d %B %Y %H:%M ").capitalize()

        if check_key(episode, 'seasonNumber'):
            label += unicode(episode['seasonNumber'])

        if check_key(episode, 'episodeNumber'):
            if len(label) > 0:
                label += "."

            label += unicode(episode['episodeNumber'])

        if check_key(episode, 'title'):
            if len(label) > 0:
                label += " - "

            label += episode['title']

        if not 'http' in episode['image']:
            image_split = episode['image'].rsplit('/', 1)

            if len(image_split) == 2:
                episode['image'] = '{image_url}/thumbnails/hd1080/{image}'.format(image_url=CONST_IMAGE_URL, image=episode['image'].rsplit('/', 1)[1])
            else:
                episode['image'] = '{image_url}/{image}'.format(image_url=CONST_IMAGE_URL, image=episode['image'])

        items.append(plugin.Item(
            label = label,
            info = {
                'plot': episode['desc'],
                'duration': episode['duration'],
                'mediatype': 'video',
            },
            art = {
                'thumb': episode['image'],
                'fanart': episode['image']
            },
            path = plugin.url_for(func_or_url=play_video, type='vod', channel=None, id=episode['id'], _is_live=False),
            playable = True,
        ))

    folder.add_items(items)

    if _debug_mode:
        log.debug('Execution Done: plugin.vod_season')

    return folder

@plugin.route()
def search_menu(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.search_menu')

    folder = plugin.Folder(title=_.SEARCHMENU)
    label = _.NEWSEARCH

    folder.add_item(
        label = label,
        info = {'plot': _.NEWSEARCHDESC},
        path = plugin.url_for(func_or_url=search),
    )

    folder.add_item(
        label= label + " (Online)",
        path=plugin.url_for(func_or_url=online_search)
    )

    for x in range(1, 10):
        searchstr = settings.get(key='_search' + unicode(x))

        if searchstr != '':
            type = settings.get(key='_search_type' + unicode(x))
            label = searchstr + type

            if type == " (Online)":
                path = plugin.url_for(func_or_url=online_search, query=searchstr)
            else:
                path = plugin.url_for(func_or_url=search, query=searchstr)

            folder.add_item(
                label = label,
                info = {'plot': _(_.SEARCH_FOR, query=searchstr)},
                path = path,
            )

    if _debug_mode:
        log.debug('Execution Done: plugin.search_menu')

    return folder

@plugin.route()
def search(query=None, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.search')
        log.debug('Vars: query={query}'.format(query=query))

    items = []

    if not query:
        query = gui.input(message=_.SEARCH, default='').strip()

        if not query:
            return

        for x in reversed(list(range(2, 10))):
            settings.set(key='_search' + unicode(x), value=settings.get(key='_search' + unicode(x - 1)))

        settings.set(key='_search1', value=query)

    folder = plugin.Folder(title=_(_.SEARCH_FOR, query=query))

    data = load_file(file='list_replay.json', isJSON=True)
    processed = process_replaytv_search(data=data, start=0, search=query)
    items += processed['items']

    processed = process_vod_content(data=load_file(file='vod.json', isJSON=True)['series'], start=0, search=query, type=_.SERIES)
    items += processed['items']
    processed = process_vod_content(data=load_file(file='vod.json', isJSON=True)['movies'], start=0, search=query, type=_.MOVIES)
    items += processed['items']

    items[:] = sorted(items, key=_sort_replay_items, reverse=True)
    items = items[:25]

    folder.add_items(items)

    if _debug_mode:
        log.debug('Execution Done: plugin.search')

    return folder

@plugin.route()
def online_search(query=None, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.online_search')
        log.debug('Vars: query={query}'.format(query=query))

    if not query:
        query = gui.input(message=_.SEARCH, default='').strip()

        if not query:
            return

        for x in reversed(list(range(2, 10))):
            settings.set(key='_search' + unicode(x), value=settings.get(key='_search' + unicode(x - 1)))
            settings.set(key='_search_type' + unicode(x), value=settings.get(key='_search_type' + unicode(x - 1)))

        settings.set(key='_search1', value=query)
        settings.set(key='_search_type1', value=' (Online)')

    folder = plugin.Folder(title=_(_.SEARCH_FOR, query=query))

    data = api.search(query=query)

    if not data:
        return folder

    processed = process_vod_content(data=data, start=0, type='Online', character=None)

    if check_key(processed, 'items'):
        folder.add_items(processed['items'])

    if _debug_mode:
        log.debug('Execution Done: plugin.online_search')

    return folder

@plugin.route()
def settings_menu(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.settings_menu')

    folder = plugin.Folder(title=_.SETTINGS)

    if plugin.logged_in:
        folder.add_item(label=_.CHANNEL_PICKER, path=plugin.url_for(func_or_url=channel_picker_menu))

    folder.add_item(label=_.SET_IPTV, path=plugin.url_for(func_or_url=plugin._set_settings_iptv))
    folder.add_item(label=_.SET_KODI, path=plugin.url_for(func_or_url=plugin._set_settings_kodi))
    folder.add_item(label=_.DOWNLOAD_SETTINGS, path=plugin.url_for(func_or_url=plugin._download_settings))
    folder.add_item(label=_.DOWNLOAD_EPG, path=plugin.url_for(func_or_url=plugin._download_epg))
    folder.add_item(label=_.INSTALL_WV_DRM, path=plugin.url_for(func_or_url=plugin._ia_install))
    folder.add_item(label=_.RESET_SESSION, path=plugin.url_for(func_or_url=logout, delete=False))
    folder.add_item(label=_.RESET, path=plugin.url_for(func_or_url=reset_addon))

    if plugin.logged_in:
        folder.add_item(label=_.LOGOUT, path=plugin.url_for(func_or_url=logout))

    folder.add_item(label="Addon " + _.SETTINGS, path=plugin.url_for(func_or_url=plugin._settings))

    if _debug_mode:
        log.debug('Execution Done: plugin.settings_menu')

    return folder

@plugin.route()
def channel_picker_menu(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.channel_picker_menu')

    folder = plugin.Folder(title=_.CHANNEL_PICKER)

    folder.add_item(label=_.LIVE_TV, path=plugin.url_for(func_or_url=channel_picker, type='live'))
    folder.add_item(label=_.CHANNELS, path=plugin.url_for(func_or_url=channel_picker, type='replay'))
    folder.add_item(label=_.SIMPLEIPTV, path=plugin.url_for(func_or_url=channel_picker, type='epg'))

    if _debug_mode:
        log.debug('Execution Done: plugin.channel_picker_menu')

    return folder

@plugin.route()
def channel_picker(type, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.channel_picker')

    if type=='live':
        title = _.LIVE_TV
        rows = get_live_channels(addon=False)
    elif type=='replay':
        title = _.CHANNELS
        rows = get_replay_channels()
    else:
        title = _.SIMPLEIPTV
        rows = get_live_channels(addon=False)

    folder = plugin.Folder(title=title)
    prefs = load_file(file="channel_prefs.json", isJSON=True)
    results = load_file(file="channel_test.json", isJSON=True)
    type = unicode(type)

    if not results:
        results = {}

    for row in rows:
        id = unicode(row['channel'])

        if not prefs or not check_key(prefs, id) or not check_key(prefs[id], type) or prefs[id][type] == 'true':
            color = 'green'
        else:
            color = 'red'

        label = _(row['label'], _bold=True, _color=color)

        if check_key(results, id):
            if results[id][type] == 'true':
                label += _(' (' + _.TEST_SUCCESS + ')', _bold=False, _color='green')
            else:
                label += _(' (' + _.TEST_FAILED + ')', _bold=False, _color='red')
        else:
            label += _(' (' + _.NOT_TESTED + ')', _bold=False, _color='orange')

        if not prefs or not check_key(prefs, id) or not check_key(prefs[id], type + '_choice') or prefs[id][type + '_choice'] == 'auto':
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
                (_.TEST_CHANNEL, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=test_channel, channel=id)), ),
            ],
            playable = False,
        )

    if _debug_mode:
        log.debug('Execution Done: plugin.channel_picker')

    return folder

@plugin.route()
def test_channel(channel, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.test_channel')

    while not api._abortRequested and not xbmc.Monitor().abortRequested() and settings.getBool(key='_test_running'):
        settings.setInt(key='_last_playing', value=time.time())

        if xbmc.Monitor().waitForAbort(1):
            api._abortRequested = True
            break

    if api._abortRequested or xbmc.Monitor().abortRequested():
        return None

    settings.setInt(key='_last_playing', value=0)
    api.test_channels(tested=True, channel=channel)

    if _debug_mode:
        log.debug('Execution Done: plugin.test_channel')

@plugin.route()
def change_channel(type, id, change, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.change_channel')

    if not id or len(unicode(id)) == 0 or not type or len(unicode(type)) == 0:
        return False

    prefs = load_file(file="channel_prefs.json", isJSON=True)
    id = unicode(id)
    type = unicode(type)

    if not prefs:
        prefs = {}

    if change == 'False':
        prefs[id][unicode(type) + '_choice'] = 'manual'

        if not check_key(prefs, id):
            prefs[id] = {}
            prefs[id][type] = 'false'
        else:
            if prefs[id][type] == 'true':
                prefs[id][type] = 'false'
            else:
                prefs[id][type] = 'true'
    else:
        prefs[id][unicode(type) + '_choice'] = 'auto'
        results = load_file(file="channel_test.json", isJSON=True)

        if not results:
            results = {}

        if check_key(results, id):
            if results[id][type] == 'true':
                prefs[id][type] = 'true'
            else:
                prefs[id][type] = 'false'
        else:
            prefs[id][type] = 'true'

    write_file(file="channel_prefs.json", data=prefs, isJSON=True)

    if type == 'epg':
        api.create_playlist()


    xbmc.executeJSONRPC('{{"jsonrpc":"2.0","id":1,"method":"GUI.ActivateWindow","params":{{"window":"videos","parameters":["plugin://' + unicode(ADDON_ID) + '/?_=channel_picker&type=' + type + '"]}}}}')

    if _debug_mode:
        log.debug('Execution Done: plugin.change_channel')

@plugin.route()
def reset_addon(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.reset_addon')

    plugin._reset()
    logout(delete=True)

    if _debug_mode:
        log.debug('Execution Done: plugin.reset_addon')

@plugin.route()
def logout(delete=True, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.logout')
        log.debug('Vars: delete={delete}'.format(delete=delete))

    if not delete == 'False':
        if not gui.yes_no(message=_.LOGOUT_YES_NO):
            return

        settings.remove(key='_username')
        settings.remove(key='_pswd')

    api.clear_session()
    api.new_session(force=True, channels=True)
    plugin.logged_in = api.logged_in
    gui.refresh()

    if _debug_mode:
        log.debug('Execution Done: plugin.logout')

@plugin.route()
@plugin.login_required()
def play_video(type=None, channel=None, id=None, from_beginning='False', **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.play_video')
        log.debug('Vars: type={type}, channel={channel}, id={id}, title={title}, from_beginning={from_beginning}'.format(type=type, channel=channel, id=id, title=title, from_beginning=from_beginning))

    CDMHEADERS = {}
    properties = {}
    friendly = ''

    if not type and not len(unicode(type)) > 0:
        return False

    if type == 'program':
        properties['seekTime'] = 1

    rows = load_file(file='channels.json', isJSON=True)

    if rows:
        channelno = 0

        for row in rows:
            channelno += 1
            channeldata = api.get_channel_data(row=row, channelno=channelno)

            if channeldata['channel_id'] == channel:
                friendly = channeldata['channel_friendly']
                break

    playdata = api.play_url(type=type, channel=channel, friendly=friendly, id=id, from_beginning=from_beginning)

    if not playdata or not check_key(playdata, 'path') or not check_key(playdata, 'license'):
        return False

    if check_key(playdata, 'license') and check_key(playdata['license'], 'drmConfig') and check_key(playdata['license']['drmConfig'], 'widevine'):
        if 'nlznl.solocoo.tv' in playdata['license']['drmConfig']['widevine']['drmServerUrl']:
            if xbmc.Monitor().waitForAbort(1):
                return False

        if check_key(playdata['license']['drmConfig']['widevine'], 'customHeaders'):
            for row in playdata['license']['drmConfig']['widevine']['customHeaders']:
                CDMHEADERS[row] = playdata['license']['drmConfig']['widevine']['customHeaders'][row]

        item_inputstream = inputstream.Widevine(
            license_key = playdata['license']['drmConfig']['widevine']['drmServerUrl'],
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
    credits = []

    if check_key(playdata['info'], 'Start') and check_key(playdata['info'], 'End'):
        startT = datetime.datetime.fromtimestamp(time.mktime(time.strptime(playdata['info']['Start'], "%Y-%m-%dT%H:%M:%S")))
        startT = convert_datetime_timezone(startT, "UTC", "UTC")
        endT = datetime.datetime.fromtimestamp(time.mktime(time.strptime(playdata['info']['End'], "%Y-%m-%dT%H:%M:%S")))
        endT = convert_datetime_timezone(endT, "UTC", "UTC")

        if check_key(playdata['info'], 'DurationInSeconds'):
            duration = playdata['info']['DurationInSeconds']
        elif check_key(playdata['info'], 'Duur'):
            duration = playdata['info']['Duur']
        else:
            duration = int((endT - startT).total_seconds())

        if xbmc.getLanguage(xbmc.ISO_639_1) == 'nl':
            itemlabel = '{weekday} {day} {month} {yearhourminute} '.format(weekday=date_to_nl_dag(startT), day=startT.strftime("%d"), month=date_to_nl_maand(startT), yearhourminute=startT.strftime("%Y %H:%M"))
        else:
            itemlabel = startT.strftime("%A %d %B %Y %H:%M ").capitalize()

        itemlabel += " - "
    elif check_key(playdata['info'], 'Duur'):
        duration = playdata['info']['Duur']

    if check_key(playdata['info'], 'Title'):
        itemlabel += playdata['info']['Title']
        label2 = playdata['info']['Title']
    elif check_key(playdata['info'], 'Serie') and check_key(playdata['info']['Serie'], 'Titel') and len(playdata['info']['Serie']['Titel']):
        itemlabel += playdata['info']['Serie']['Titel']
        label2 = playdata['info']['Serie']['Titel']

        if check_key(playdata['info'], 'Titel') and len(playdata['info']['Titel']) > 0 and playdata['info']['Titel'] != playdata['info']['Serie']['Titel']:
            itemlabel += ": " + playdata['info']['Titel']
            label2 += ": " + playdata['info']['Titel']
    elif check_key(playdata['info'], 'Titel'):
        itemlabel += playdata['info']['Titel']
        label2 = playdata['info']['Titel']

    if check_key(playdata['info'], 'LongDescription'):
        description = playdata['info']['LongDescription']
    elif check_key(playdata['info'], 'Omschrijving'):
        description = playdata['info']['Omschrijving']

    if check_key(playdata['info'], 'CoverUrl'):
        program_image = playdata['info']['CoverUrl']
        program_image_large = playdata['info']['CoverUrl']
    elif check_key(playdata['info'], 'AfbeeldingUrl'):
        program_image = playdata['info']['AfbeeldingUrl']
        program_image_large = playdata['info']['AfbeeldingUrl']

    if check_key(playdata['info'], 'ChannelTitle'):
        label2 += " - "  + playdata['info']['ChannelTitle']
    elif check_key(playdata['info'], 'Zender'):
        label2 += " - "  + playdata['info']['Zender']

    settings.setInt(key='_stream_duration', value=duration)

    listitem = plugin.Item(
        label = itemlabel,
        label2 = label2,
        art = {
            'thumb': program_image,
            'fanart': program_image_large
        },
        info = {
            'credits': credits,
            'cast': cast,
            'writer': writer,
            'director': director,
            'plot': description,
            'duration': duration,
            'mediatype': 'video',
        },
        properties = properties,
        path = playdata['path'],
        headers = CDMHEADERS,
        inputstream = item_inputstream,
    )

    if _debug_mode:
        log.debug('Execution Done: plugin.play_video')

    return listitem

@plugin.route()
@plugin.login_required()
def switchChannel(channel_uid, **kwargs):
    play_url = 'PlayMedia(pvr://channels/tv/{allchan}/{backend}_{channel_uid}.pvr)'.format(allchan=xbmc.getLocalizedString(19287), backend=backend, channel_uid=channel_uid)

    if _debug_mode:
        log.debug('Executing: plugin.switchChannel')
        log.debug('Vars: channel_uid={channel_uid}'.format(channel_uid=channel_uid))
        log.debug('Play URL: {play_url}'.format(play_url=play_url))

    xbmc.executebuiltin(play_url)

    if _debug_mode:
        log.debug('Execution Done: plugin.switchChannel')

@signals.on(signals.BEFORE_DISPATCH)
def before_dispatch():
    api.new_session()
    plugin.logged_in = api.logged_in

#Support functions
def first_boot():
    if _debug_mode:
        log.debug('Executing: plugin.first_boot')

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

    settings.setBool(key='_first_boot', value=False)
    _first_boot = False

    if _debug_mode:
        log.debug('Execution Done: plugin.first_boot')

def get_live_channels(addon=False, retry=True):
    if _debug_mode:
        log.debug('Executing: plugin.get_live_channels')
        log.debug('Vars: addon={addon}, retry={retry}'.format(addon=addon, retry=retry))

    global backend, query_channel
    channels = []
    pvrchannels = []

    rows = load_file(file='channels.json', isJSON=True)

    if rows:
        if addon:
            query_addons = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddons", "params": {"type": "xbmc.pvrclient"}}'))

            if check_key(query_addons, 'result') and check_key(query_addons['result'], 'addons'):
                addons = query_addons['result']['addons']
                backend = addons[0]['addonid']

                query_channel = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "PVR.GetChannels", "params": {"channelgroupid": "alltv", "properties" :["uniqueid"]},"id": 1}'))

                if check_key(query_channel, 'result') and check_key(query_channel['result'], 'channels'):
                    pvrchannels = query_channel['result']['channels']

        channelno = 0

        for row in rows:
            channelno += 1
            channeldata = api.get_channel_data(row=row, channelno=channelno)

            path = plugin.url_for(func_or_url=play_video, type='channel', channel=channeldata['channel_id'], id=None, _is_live=True)
            playable = True

            for channel in pvrchannels:
                if channel['label'] == channeldata['label']:
                    channel_uid = channel['uniqueid']
                    path = plugin.url_for(func_or_url=switchChannel, channel_uid=channel_uid)
                    playable = False
                    break

            if (len(unicode(channeldata['channel_id'])) > 0):
                channels.append({
                    'label': channeldata['label'],
                    'channel': channeldata['channel_id'],
                    'chno': channeldata['channel_number'],
                    'description': channeldata['description'],
                    'image': channeldata['station_image_large'],
                    'path':  path,
                    'playable': playable,
                    'context': [
                        (_.START_BEGINNING, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=play_video, type='channel', channel=channeldata['channel_id'], id=None, from_beginning=True)), ),
                    ],
                })

        channels[:] = sorted(channels, key=_sort_live)

    if len(channels) == 0 and retry:
        logout(delete=False)

        if plugin.logged_in:
            channels = get_live_channels(addon=addon, retry=False)

    if _debug_mode:
        log.debug('Execution Done: plugin.get_live_channels')

    return channels

def get_replay_channels(retry=True):
    if _debug_mode:
        log.debug('Executing: plugin.get_replay_channels')
        log.debug('Vars: retry={retry}'.format(retry=retry))

    channels = []
    rows = load_file(file='channels.json', isJSON=True)

    if rows:
        channelno = 0

        for row in rows:
            channelno += 1
            channeldata = api.get_channel_data(row=row, channelno=channelno)

            if (len(unicode(channeldata['channel_id'])) > 0):
                channels.append({
                    'label': channeldata['label'],
                    'channel': channeldata['channel_id'],
                    'chno': channeldata['channel_number'],
                    'description': channeldata['description'],
                    'image': channeldata['station_image_large'],
                    'path': plugin.url_for(func_or_url=replaytv_by_day, image=channeldata['station_image_large'], description=channeldata['description'], label=channeldata['label'], station=channeldata['channel_id']),
                    'playable': False,
                    'context': [],
                })

        channels[:] = sorted(channels, key=_sort_live)

    if len(channels) == 0 and retry:
        logout(delete=False)

        if plugin.logged_in:
            channels = get_replay_channels(addon=addon, retry=False)

    if _debug_mode:
        log.debug('Execution Done: plugin.get_replay_channels')

    return channels

def process_replaytv_list(data, start=0):
    if _debug_mode:
        log.debug('Executing: plugin.process_replaytv_list')
        log.debug('Vars: data={data}, start={start}'.format(data=data, start=start))

    prefs = load_file(file="channel_prefs.json", isJSON=True)
    start = int(start)
    items = []
    count = 0
    item_count = 0
    time_now = int((datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds())

    for row in sorted(data):
        currow = data[row]

        if item_count == 51:
            break

        if count < start:
            count += 1
            continue

        count += 1

        if not check_key(currow, 'orig') or not check_key(currow, 'ids'):
            continue

        if check_key(currow, 'a') and check_key(currow, 'e') and (time_now < int(currow['a']) or time_now > int(currow['e'])):
            continue

        if check_key(currow, 'cn') and prefs and check_key(prefs, unicode(currow['cn'])) and prefs[unicode(currow['cn'])]['replay'] == 'false':
            continue

        label = currow['orig']

        items.append(plugin.Item(
            label = label,
            path = plugin.url_for(func_or_url=replaytv_item, ids=json.dumps(currow['ids']), label=label, start=0),
        ))

        item_count += 1

    returnar = {'items': items, 'count': count}

    if _debug_mode:
        log.debug('Returned Data: {returnar}'.format(returnar=returnar))
        log.debug('Execution Done: plugin.process_replaytv_list')

    return returnar

def process_replaytv_search(data, start=0, search=None):
    if _debug_mode:
        log.debug('Executing: plugin.process_replaytv_search')
        log.debug('Vars: data={data}, start={start}, search={search}'.format(data=data, start=start, search=search))

    prefs = load_file(file="channel_prefs.json", isJSON=True)
    start = int(start)
    items = []
    count = 0
    item_count = 0
    time_now = int((datetime.datetime.utcnow() - datetime.datetime(1970, 1, 1)).total_seconds())

    for row in data:
        letter_row = data[row]

        for row2 in letter_row:
            currow = data[row][row2]

            if item_count == 51:
                break

            if count < start:
                count += 1
                continue

            count += 1

            if not check_key(currow, 'orig') or not check_key(currow, 'ids'):
                continue

            if check_key(currow, 'a') and check_key(currow, 'e') and (time_now < int(currow['a']) or time_now > int(currow['e'])):
                continue

            if check_key(currow, 'cn') and prefs and check_key(prefs, unicode(currow['cn'])) and prefs[unicode(currow['cn'])]['replay'] == 'false':
                continue

            label = currow['orig'] + ' (ReplayTV)'

            fuzz_set = fuzz.token_set_ratio(label, search)
            fuzz_partial = fuzz.partial_ratio(label, search)
            fuzz_sort = fuzz.token_sort_ratio(label, search)

            if (fuzz_set + fuzz_partial + fuzz_sort) > 160:
                items.append(plugin.Item(
                    label = label,
                    properties = {"fuzz_set": fuzz_set, "fuzz_sort": fuzz_sort, "fuzz_partial": fuzz_partial, "fuzz_total": fuzz_set + fuzz_partial + fuzz_sort},
                    path = plugin.url_for(func_or_url=replaytv_item, ids=json.dumps(currow['ids']), label=label, start=0),
                ))

                item_count += 1

    returnar = {'items': items, 'count': count}

    if _debug_mode:
        log.debug('Returned Data: {returnar}'.format(returnar=returnar))
        log.debug('Execution Done: plugin.process_replaytv_search')

    return returnar

def process_replaytv_content(data, day=0, start=0):
    if _debug_mode:
        log.debug('Executing: plugin.process_replaytv_content')
        log.debug('Vars: data={data}, day={day}, start={start}'.format(data=data, day=day, start=start))

    day = int(day)
    start = int(start)
    curdate = datetime.date.today() - datetime.timedelta(days=day)

    startDate = convert_datetime_timezone(datetime.datetime(curdate.year, curdate.month, curdate.day, 0, 0, 0), "Europe/Amsterdam", "UTC")
    endDate = convert_datetime_timezone(datetime.datetime(curdate.year, curdate.month, curdate.day, 23, 59, 59), "Europe/Amsterdam", "UTC")
    startTime = startDate.strftime("%Y%m%d%H%M%S")
    endTime = endDate.strftime("%Y%m%d%H%M%S")

    items = []
    count = 0
    item_count = 0

    for row in data:
        currow = data[row]

        if item_count == 51:
            break

        if count < start:
            count += 1
            continue

        count += 1

        if not check_key(currow, 's') or not check_key(currow, 't') or not check_key(currow, 'c') or not check_key(currow, 'e'):
            continue

        startsplit = unicode(currow['s'].split(' ', 1)[0])
        endsplit = unicode(currow['e'].split(' ', 1)[0])

        if not startsplit.isdigit() or not len(startsplit) == 14 or startsplit < startTime or not endsplit.isdigit() or not len(endsplit) == 14 or startsplit >= endTime:
            continue

        startT = datetime.datetime.fromtimestamp(time.mktime(time.strptime(startsplit, "%Y%m%d%H%M%S")))
        startT = convert_datetime_timezone(startT, "UTC", "Europe/Amsterdam")
        endT = datetime.datetime.fromtimestamp(time.mktime(time.strptime(endsplit, "%Y%m%d%H%M%S")))
        endT = convert_datetime_timezone(endT, "UTC", "Europe/Amsterdam")

        if endT < (datetime.datetime.now(pytz.timezone("Europe/Amsterdam")) - datetime.timedelta(days=7)):
            continue

        label = startT.strftime("%H:%M") + " - " + currow['t']
        description = ''
        channel = ''
        program_image = ''
        program_image_large = ''

        if check_key(currow, 'desc'):
            description = currow['desc']

        duration = int((endT - startT).total_seconds())

        if check_key(currow, 'i'):
            program_image = currow['i']

        if check_key(currow, 'h'):
            program_image_large = currow['h']
        else:
            program_image_large = program_image

        if check_key(currow, 'c'):
            channel = currow['c']

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
            path = plugin.url_for(func_or_url=play_video, type='program', channel=channel, id=row, duration=duration, _is_live=False),
            playable = True,
        ))

        item_count += 1

    returnar = {'items': items, 'count': count}

    if _debug_mode:
        log.debug('Returned Data: {returnar}'.format(returnar=returnar))
        log.debug('Execution Done: plugin.process_replaytv_content')

    return returnar

def process_replaytv_list_content(data, ids, start=0):
    if _debug_mode:
        log.debug('Executing: plugin.process_replaytv_list_content')
        log.debug('Vars: data={data}, ids={ids}, start={start}'.format(data=data, ids=ids, start=start))

    start = int(start)
    items = []
    count = 0
    item_count = 0

    ids = json.loads(ids)
    totalrows = len(ids)

    for id in ids:
        currow = data[id]

        if item_count == 51:
            break

        if count < start:
            count += 1
            continue

        count += 1

        if not check_key(currow, 's') or not check_key(currow, 't') or not check_key(currow, 'c') or not check_key(currow, 'e'):
            continue

        startsplit = unicode(currow['s'].split(' ', 1)[0])
        endsplit = unicode(currow['e'].split(' ', 1)[0])

        if not startsplit.isdigit() or not len(startsplit) == 14 or not endsplit.isdigit() or not len(endsplit) == 14:
            continue

        startT = datetime.datetime.fromtimestamp(time.mktime(time.strptime(startsplit, "%Y%m%d%H%M%S")))
        startT = convert_datetime_timezone(startT, "UTC", "Europe/Amsterdam")
        endT = datetime.datetime.fromtimestamp(time.mktime(time.strptime(endsplit, "%Y%m%d%H%M%S")))
        endT = convert_datetime_timezone(endT, "UTC", "Europe/Amsterdam")

        if startT > datetime.datetime.now(pytz.timezone("Europe/Amsterdam")) or endT < (datetime.datetime.now(pytz.timezone("Europe/Amsterdam")) - datetime.timedelta(days=7)):
            continue

        if xbmc.getLanguage(xbmc.ISO_639_1) == 'nl':
            itemlabel = '{weekday} {day} {month} {yearhourminute} '.format(weekday=date_to_nl_dag(startT), day=startT.strftime("%d"), month=date_to_nl_maand(startT), yearhourminute=startT.strftime("%Y %H:%M"))
        else:
            itemlabel = startT.strftime("%A %d %B %Y %H:%M ").capitalize()

        itemlabel += currow['t'] + " (" + currow['cn'] + ")"
        channel = ''
        description = ''
        program_image = ''
        program_image_large = ''

        if check_key(currow, 'desc'):
            description = currow['desc']

        duration = int((endT - startT).total_seconds())

        if check_key(currow, 'i'):
            program_image = currow['i']

        if check_key(currow, 'h'):
            program_image_large = currow['h']
        else:
            program_image_large = program_image

        if check_key(currow, 'c'):
            channel = currow['c']

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
            path = plugin.url_for(func_or_url=play_video, type='program', channel=channel, id=id, duration=duration, _is_live=False),
            playable = True,
        ))

        item_count = item_count + 1

    returnar = {'items': items, 'totalrows': totalrows, 'count': count}

    if _debug_mode:
        log.debug('Returned Data: {returnar}'.format(returnar=returnar))
        log.debug('Execution Done: plugin.process_replaytv_list_content')

    return returnar

def process_vod_content(data, start=0, search=None, type=None, character=None):
    if _debug_mode:
        log.debug('Executing: plugin.process_vod_content')
        log.debug('Vars: data={data}, start={start}, search={search}, type={type}, character={character}'.format(data=data, start=start, search=search, type=type, character=character))

    start = int(start)
    items = []
    count = 0
    item_count = 0

    data[:] = sorted(data, key=_sort_vod)

    for row in data:
        currow = row

        if item_count == 50:
            break

        if count < start:
            count += 1
            continue

        count += 1

        if not check_key(currow, 'id') or not check_key(currow, 'title'):
            continue

        id = currow['id']
        label = ''

        if check_key(currow, 'start'):
            if len(currow['start']) > 0:
                startT = datetime.datetime.fromtimestamp(time.mktime(time.strptime(currow['start'], "%Y-%m-%dT%H:%M:%S")))
                startT = convert_datetime_timezone(startT, "UTC", "UTC")

                if xbmc.getLanguage(xbmc.ISO_639_1) == 'nl':
                    label += '{weekday} {day} {month} {yearhourminute} '.format(weekday=date_to_nl_dag(startT), day=startT.strftime("%d"), month=date_to_nl_maand(startT), yearhourminute=startT.strftime("%Y %H:%M"))
                else:
                    label += startT.strftime("%A %d %B %Y %H:%M ").capitalize()

        label += currow['title']

        if character:
            first = label[0]

            if first.isalpha():
                if first != character:
                    continue
            else:
                if character != 'other':
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

        description = ''
        program_image = ''
        program_image_large = ''
        duration = 0
        properties = []

        if check_key(currow, 'desc'):
            description = currow['desc']

        if check_key(currow, 'duration'):
            duration = int(currow['duration'])

        if check_key(currow, 'image'):
            program_image = currow['image']
            program_image_large = currow['image']

        if not check_key(currow, 'type'):
            continue

        if currow['type'] == "show" or currow['type'] == "Serie":
            path = plugin.url_for(func_or_url=vod_series, label=label, description=description, image=program_image_large, id=id)
            info = {'plot': description}
            playable = False
        elif currow['type'] == "Epg":
            path = plugin.url_for(func_or_url=play_video, type='program', channel=None, id=id, duration=duration, _is_live=False)
            info = {'plot': description, 'duration': duration, 'mediatype': 'video'}
            playable = True
        elif currow['type'] == "movie" or currow['type'] == "Vod":
            path = plugin.url_for(func_or_url=play_video, type='vod', channel=None, id=id, duration=duration, _is_live=False)
            info = {'plot': description, 'duration': duration, 'mediatype': 'video'}
            playable = True
        else:
            continue

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

        item_count += 1

    returnar = {'items': items, 'count': count}

    if _debug_mode:
        log.debug('Returned Data: {returnar}'.format(returnar=returnar))
        log.debug('Execution Done: plugin.process_vod_content')

    return returnar

def _sort_live(element):
    return element['chno']

def _sort_vod(element):
    if not 'timestamp' in element:
        return 0

    return element['timestamp']

def _sort_season(element):
    if element['seriesNumber'].isnumeric():
        return int(element['seriesNumber'])
    else:
        matches = re.findall(r"Seizoen (\d+)", element['seriesNumber'])

        for match in matches:
            return int(match)

        return 0

def _sort_episodes(element):
    try:
        return element['episodeNumber']
    except:
        return 0

def _sort_replay_items(element):
    return element.get_li().getProperty('fuzz_total')