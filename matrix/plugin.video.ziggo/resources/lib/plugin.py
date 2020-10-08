import _strptime

import datetime, json, pytz, random, requests, string, sys, time, xbmc, xbmcplugin

from fuzzywuzzy import fuzz
from resources.lib.api import API
from resources.lib.base import plugin, gui, signals, inputstream, settings
from resources.lib.base.constants import ADDON_ID
from resources.lib.base.exceptions import Error
from resources.lib.base.log import log
from resources.lib.base.util import check_key, convert_datetime_timezone, download_vod, date_to_nl_dag, date_to_nl_maand, get_credentials, load_file, write_file
from resources.lib.language import _
from resources.lib.util import get_image, get_play_url

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
_client_id = settings.get(key='_client_id')

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

        if _debug_mode:
            log.debug('Setting showMoviesSeries: {moviesseries}'.format(moviesseries=settings.getBool('showMoviesSeries')))

        if settings.getBool('showMoviesSeries'):
            folder.add_item(label=_(_.SERIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='series', label=_.SERIES, kids=0, start=0))
            folder.add_item(label=_(_.MOVIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='movies', label=_.MOVIES, kids=0, start=0))
            folder.add_item(label=_(_.HBO_SERIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='hboseries', label=_.HBO_SERIES, kids=0, start=0))
            folder.add_item(label=_(_.HBO_MOVIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='hbomovies', label=_.HBO_MOVIES, kids=0, start=0))
            folder.add_item(label=_(_.KIDS_SERIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='kids', label=_.KIDS_SERIES, kids=1, start=0))
            folder.add_item(label=_(_.KIDS_MOVIES, _bold=True), path=plugin.url_for(func_or_url=vod, file='kids', label=_.KIDS_MOVIES, kids=2, start=0))

        folder.add_item(label=_(_.WATCHLIST, _bold=True), path=plugin.url_for(func_or_url=watchlist))

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
    check_entitlements()

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
def replaytv_alphabetical(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.replaytv_alphabetical')

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

    if _debug_mode:
        log.debug('Execution Done: plugin.replaytv_alphabetical')

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
        gui.ok(_.DISABLE_ONLY_STANDARD, _.NO_REPLAY_TV_INFO)
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
def vod(file, label, kids=0, start=0, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.vod')
        log.debug('Vars: file={file}, label={label}, kids={kids}, start={start}'.format(file=file, label=label, kids=kids, start=start))

    kids = int(kids)
    start = int(start)
    folder = plugin.Folder(title=label)

    data = load_file(file='vod.json', isJSON=True)[file]

    if not data:
        return folder

    processed = process_vod_content(data=data, start=start, series=kids, type=label)

    if check_key(processed, 'items'):
        folder.add_items(processed['items'])

    if check_key(processed, 'count') and len(data) > processed['count']:
        folder.add_item(
            label = _(_.NEXT_PAGE, _bold=True),
            path = plugin.url_for(func_or_url=vod, file=file, label=label, kids=kids, start=processed['count']),
        )

    if _debug_mode:
        log.debug('Execution Done: plugin.vod')

    return folder

@plugin.route()
def vod_series(label, description, image, image_large, seasons, mediagroupid=None, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.vod_series')
        log.debug('Vars: label={label}, description={description}, image={image}, image_large={image_large}, seasons={seasons}, mediagroupid={mediagroupid}'.format(label=label, description=description, image=image, image_large=image_large, seasons=seasons, mediagroupid=mediagroupid))

    folder = plugin.Folder(title=label)

    items = []
    context = []

    seasons = json.loads(seasons)

    if mediagroupid:
        context.append((_.ADD_TO_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=add_to_watchlist, id=mediagroupid, type='group')), ))

    title = label

    for season in seasons:
        label = _.SEASON + " " + unicode(season['seriesNumber'])

        items.append(plugin.Item(
            label = label,
            info = {'plot': description},
            art = {
                'thumb': image,
                'fanart': image_large
            },
            path = plugin.url_for(func_or_url=vod_season, label=label, title=title, id=season['id'], mediagroupid=mediagroupid),
            context = context,
        ))

    folder.add_items(items)

    if _debug_mode:
        log.debug('Execution Done: plugin.vod_series')

    return folder

@plugin.route()
def vod_season(label, title, id, mediagroupid=None, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.vod_season')
        log.debug('Vars: label={label}, title={title}, id={id}, mediagroupid={mediagroupid}'.format(label=label, title=title, id=id, mediagroupid=mediagroupid))

    folder = plugin.Folder(title=label)

    season_url = '{mediaitems_url}?byMediaType=Episode%7CFeatureFilm&byParentId={id}&includeAdult=true&range=1-1000&sort=seriesEpisodeNumber|ASC'.format(mediaitems_url=settings.get(key='_mediaitems_url'), id=id)
    data = api.download(url=season_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

    if not data or not check_key(data, 'mediaItems'):
        return folder

    processed = process_vod_season(data=data, title=title, mediagroupid=mediagroupid)

    if processed:
        folder.add_items(processed)

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

    base_v3 = settings.getBool(key='_base_v3')

    if not base_v3:
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
                if not base_v3:
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
            settings.set(key='_search_type' + unicode(x), value=settings.get(key='_search_type' + unicode(x - 1)))

        settings.set(key='_search1', value=query)
        settings.set(key='_search_type1', value='')

    folder = plugin.Folder(title=_(_.SEARCH_FOR, query=query))

    data = load_file(file='list_replay.json', isJSON=True)
    processed = process_replaytv_search(data=data, start=0, search=query)
    items += processed['items']

    if settings.getBool('showMoviesSeries'):
        processed = process_vod_content(data=load_file(file='vod.json', isJSON=True)['series'], start=0, series=0, search=query, type=_.SERIES)
        items += processed['items']
        processed = process_vod_content(data=load_file(file='vod.json', isJSON=True)['movies'], start=0, series=0, search=query, type=_.MOVIES)
        items += processed['items']
        processed = process_vod_content(data=load_file(file='vod.json', isJSON=True)['hboseries'], start=0, series=0, search=query, type=_.HBO_SERIES)
        items += processed['items']
        processed = process_vod_content(data=load_file(file='vod.json', isJSON=True)['hbomovies'], start=0, series=0, search=query, type=_.HBO_MOVIES)
        items += processed['items']
        processed = process_vod_content(data=load_file(file='vod.json', isJSON=True)['kids'], start=0, series=1, search=query, type=_.KIDS_SERIES)
        items += processed['items']
        processed = process_vod_content(data=load_file(file='vod.json', isJSON=True)['kids'], start=0, series=2, search=query, type=_.KIDS_MOVIES)
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

    data = api.online_search(search=query)

    if data:
        if not settings.getBool('showMoviesSeries'):
            try:
                data.pop('moviesAndSeries', None)
            except:
                pass

        processed = process_online_search(data=data)

        if processed:
            folder.add_items(processed)

    if _debug_mode:
        log.debug('Execution Done: plugin.online_search')

    return folder

@plugin.route()
def settings_menu(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.settings_menu')

    folder = plugin.Folder(title=_.SETTINGS)

    if plugin.logged_in:
        folder.add_item(label=_.CHECK_ENTITLEMENTS, path=plugin.url_for(func_or_url=check_entitlements))
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
        settings.remove(key='_household_id')
        settings.remove(key='_profile_id')
        settings.remove(key='_pswd')

    settings.remove(key='_access_token')
    api.new_session(force=True, channels=True)
    plugin.logged_in = api.logged_in
    gui.refresh()

    if _debug_mode:
        log.debug('Execution Done: plugin.logout')

@plugin.route()
@plugin.login_required()
def play_video(type=None, channel=None, id=None, title=None, from_beginning='False', **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.play_video')
        log.debug('Vars: type={type}, channel={channel}, id={id}, title={title}, from_beginning={from_beginning}'.format(type=type, channel=channel, id=id, title=title, from_beginning=from_beginning))

    properties = {
        'seekTime': 1
    }

    if not type or not len(unicode(type)) > 0 or not id or not len(unicode(id)) > 0:
        return False

    playdata = api.play_url(type=type, id=id, from_beginning=from_beginning)

    if type == "channel" and not playdata['type'] == "program":
        properties.pop('seekTime')

    if not check_key(playdata, 'path') or not check_key(playdata, 'license') or not check_key(playdata, 'token') or not check_key(playdata, 'locator'):
        return False

    creds = get_credentials()

    CDMHEADERS = {
        'User-Agent': _user_agent,
        'X-Client-Id': _client_id + '||' + _user_agent,
        'X-OESP-Token': api._access_token,
        'X-OESP-Username': api._username,
        'X-OESP-License-Token': api._drm_token,
        'X-OESP-DRM-SchemeIdUri': 'urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed',
        'X-OESP-Content-Locator': playdata['locator'],
    }

    item_inputstream = inputstream.Widevine(
        license_key = playdata['license'],
        media_renewal_url = plugin.url_for(func_or_url=renew_token, id=playdata['path'], locator=playdata['locator']),
        media_renewal_time = 60,
    )

    itemlabel = ''
    label2 = ''
    description = ''
    program_image = ''
    program_image_large = ''
    duration = 0
    year = ''
    cast = []
    director = []
    genres = []
    epcode = ''

    if check_key(playdata, 'info'):
        if check_key(playdata['info'], 'latestBroadcastEndTime') and check_key(playdata['info'], 'latestBroadcastStartTime'):
            startsplit = int(playdata['info']['latestBroadcastStartTime']) // 1000
            endsplit = int(playdata['info']['latestBroadcastEndTime']) // 1000
            duration = endsplit - startsplit

            startT = datetime.datetime.fromtimestamp(startsplit)
            startT = convert_datetime_timezone(startT, "UTC", "UTC")
            endT = datetime.datetime.fromtimestamp(endsplit)
            endT = convert_datetime_timezone(endT, "UTC", "UTC")

            if xbmc.getLanguage(xbmc.ISO_639_1) == 'nl':
                itemlabel = '{weekday} {day} {month} {yearhourminute} '.format(weekday=date_to_nl_dag(startT), day=startT.strftime("%d"), month=date_to_nl_maand(startT), yearhourminute=startT.strftime("%Y %H:%M"))
            else:
                itemlabel = startT.strftime("%A %d %B %Y %H:%M ").capitalize()

        if title:
            itemlabel += title + ' - ' + playdata['info']['title']
        else:
            itemlabel += playdata['info']['title']

        if check_key(playdata['info'], 'duration'):
            duration = int(playdata['info']['duration'])
        elif check_key(playdata['info'], 'latestBroadcastStartTime') and check_key(playdata['info'], 'latestBroadcastEndTime'):
            duration = int(int(playdata['info']['latestBroadcastEndTime']) - int(playdata['info']['latestBroadcastStartTime'])) // 1000

        if check_key(playdata['info'], 'description'):
            description = playdata['info']['description']

        if check_key(playdata['info'], 'duration'):
            duration = int(playdata['info']['duration'])

        if check_key(playdata['info'], 'year'):
            year = int(playdata['info']['year'])

        if check_key(playdata['info'], 'images'):
            program_image = get_image("boxart", playdata['info']['images'])
            program_image_large = get_image("HighResLandscape", playdata['info']['images'])

            if program_image_large == '':
                program_image_large = program_image
            else:
                program_image_large += '?w=1920&mode=box'

        if check_key(playdata['info'], 'categories'):
            for categoryrow in playdata['info']['categories']:
                genres.append(categoryrow['title'])

        if check_key(playdata['info'], 'cast'):
            for castrow in playdata['info']['cast']:
                cast.append(castrow)

        if check_key(playdata['info'], 'directors'):
            for directorrow in playdata['info']['directors']:
                director.append(directorrow)

        if check_key(playdata['info'], 'seriesNumber'):
            epcode += 'S' + unicode(playdata['info']['seriesNumber'])

        if check_key(playdata['info'], 'seriesEpisodeNumber'):
            epcode += 'E' + unicode(playdata['info']['seriesEpisodeNumber'])

        if check_key(playdata['info'], 'secondaryTitle'):
            label2 = playdata['info']['secondaryTitle']

            if len(epcode) > 0:
                label2 += " (" + epcode + ")"
        else:
            label2 = playdata['info']['title']

        rows = load_file(file='channels.json', isJSON=True)

        if rows:
            for row in rows:
                channeldata = api.get_channel_data(row=row)

                if channeldata['channel_id'] == channel:
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
            'director': director,
            'genre': genres,
            'plot': description,
            'duration': duration,
            'mediatype': 'video',
            'year': year,
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

@plugin.route()
@plugin.login_required()
def renew_token(id=None, locator=None, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.renew_token')
        log.debug('Vars: id={id}, locator={locator}'.format(id=id, locator=locator))

    api.get_play_token(locator=locator, path=id)

    id = id.replace("/manifest.mpd", "/")

    splitid = id.split('/Manifest?device', 1)

    if len(splitid) == 2:
        id = splitid[0] + "/"

    listitem = plugin.Item(
        path = id,
    )

    newItem = listitem.get_li()

    xbmcplugin.addDirectoryItem(ADDON_HANDLE, id, newItem)
    xbmcplugin.endOfDirectory(ADDON_HANDLE, cacheToDisc=False)

    if xbmc.Monitor().waitForAbort(0.1):
        return None

    if _debug_mode:
        log.debug('Execution Done: plugin.renew_token')

@plugin.route()
def check_entitlements(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.check_entitlements')

    if plugin.logged_in:
        base_v3 = settings.getBool(key='_base_v3')

        if not base_v3:
            media_groups_url = '{mediagroups_url}/lgi-nl-vod-myprime-movies?byHasCurrentVod=true&range=1-1&sort=playCount7%7Cdesc'.format(mediagroups_url=settings.get('_mediagroupsfeeds_url'))
        else:
            media_groups_url = '{mediagroups_url}/crid:~~2F~~2Fschange.com~~2Fdc30ecd3-4701-4993-993b-9ad4ff5fc301?byHasCurrentVod=true&range=1-1&sort=playCount7%7Cdesc'.format(mediagroups_url=settings.get('_mediagroupsfeeds_url'))

        data = api.download(url=media_groups_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

        if not data or not check_key(data, 'entryCount'):
            gui.ok(message=_.NO_MOVIES_SERIES, heading=_.CHECKED_ENTITLEMENTS)
            settings.setBool(key='showMoviesSeries', value=False)
            return

        id = data['mediaGroups'][0]['id']

        media_item_url = '{mediaitem_url}/{mediaitem_id}'.format(mediaitem_url=settings.get(key='_mediaitems_url'), mediaitem_id=id)
        data = api.download(url=media_item_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

        if not data:
            gui.ok(message=_.NO_MOVIES_SERIES, heading=_.CHECKED_ENTITLEMENTS)
            settings.setBool(key='showMoviesSeries', value=False)
            return

        if check_key(data, 'videoStreams'):
            urldata = get_play_url(content=data['videoStreams'])

        if (not urldata or not check_key(urldata, 'play_url') or not check_key(urldata, 'locator') or urldata['play_url'] == 'http://Playout/using/Session/Service') and base_v3:
                urldata = {}

                playout_url = '{base_url}/playout/vod/{id}?abrType=BR-AVC-DASH'.format(base_url=settings.get(key='_base_url'), id=id)
                data = api.download(url=playout_url, type="get", code=[200], data=None, json_data=False, data_return=True, return_json=True, retry=True, check_data=False)

                if not data or not check_key(data, 'url') or not check_key(data, 'contentLocator'):
                    return

                urldata['play_url'] = data['url']
                urldata['locator'] = data['contentLocator']

        if not urldata or not check_key(urldata, 'play_url') or not check_key(urldata, 'locator'):
            gui.ok(message=_.NO_MOVIES_SERIES, heading=_.CHECKED_ENTITLEMENTS)
            settings.setBool(key='showMoviesSeries', value=False)
            return

        token = api.get_play_token(locator=urldata['locator'], path=urldata['play_url'], force=True)

        if not token or not len(token) > 0:
            gui.ok(message=_.NO_MOVIES_SERIES, heading=_.CHECKED_ENTITLEMENTS)
            settings.setBool(key='showMoviesSeries', value=False)
            return

        gui.ok(message=_.YES_MOVIES_SERIES, heading=_.CHECKED_ENTITLEMENTS)
        settings.setBool(key='showMoviesSeries', value=True)
        download_vod()

    if _debug_mode:
        log.debug('Execution Done: plugin.check_entitlements')

    return

@plugin.route()
def add_to_watchlist(id, type, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.add_to_watchlist')
        log.debug('Vars: id={id}, type={type}'.format(id=id, type=type))

    if api.add_to_watchlist(id=id, type=type):
        gui.notification(_.ADDED_TO_WATCHLIST)
    else:
        gui.notification(_.ADD_TO_WATCHLIST_FAILED)

    if _debug_mode:
        log.debug('Execution Done: plugin.add_to_watchlist')

@plugin.route()
def remove_from_watchlist(id, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.remove_from_watchlist')
        log.debug('Vars: id={id}'.format(id=id))

    if api.remove_from_watchlist(id=id):
        gui.refresh()
        gui.notification(_.REMOVED_FROM_WATCHLIST)
    else:
        gui.notification(_.REMOVE_FROM_WATCHLIST_FAILED)

    if _debug_mode:
        log.debug('Execution Done: plugin.remove_from_watchlist')

@plugin.route()
def watchlist(**kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.watchlist')

    folder = plugin.Folder(title=_.WATCHLIST)

    data = api.list_watchlist()

    if data and check_key(data, 'entries'):
        processed = process_watchlist(data=data)

        if processed:
            folder.add_items(processed)

    if _debug_mode:
        log.debug('Execution Done: plugin.watchlist')

    return folder

@plugin.route()
def watchlist_listing(label, description, image, image_large, id, search=False, **kwargs):
    if _debug_mode:
        log.debug('Executing: plugin.watchlist_listing')
        log.debug('Vars: label={label}, description={description}, image={image}, image_large={image_large}, id={id}, search={search}'.format(label=label, description=description, image=image, image_large=image_large, id=id, search=search))

    folder = plugin.Folder(title=label)

    data = api.watchlist_listing(id)

    if not search:
        id = None

    if data and check_key(data, 'listings'):
        processed = process_watchlist_listing(data=data, id=id)

        if processed:
            folder.add_items(processed)

    if _debug_mode:
        log.debug('Execution Done: plugin.watchlist_listing')

    return folder

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

        for row in rows:
            channeldata = api.get_channel_data(row=row)

            path = plugin.url_for(func_or_url=play_video, type='channel', channel=channeldata['channel_id'], id=channeldata['channel_id'], title=None, _is_live=True)
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
                        (_.START_BEGINNING, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=play_video, type='channel', channel=channeldata['channel_id'], id=channeldata['channel_id'], from_beginning=True)), ),
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
        for row in rows:
            channeldata = api.get_channel_data(row=row)

            if (len(unicode(channeldata['channel_id'])) > 0):
                channels.append({
                    'label': channeldata['label'],
                    'channel': channeldata['channel_id'],
                    'chno': channeldata['channel_number'],
                    'description': channeldata['description'],
                    'image': channeldata['station_image_large'],
                    'path': plugin.url_for(func_or_url=replaytv_by_day, image=channeldata['station_image_large'], description=channeldata['description'], label=channeldata['label'], station=channeldata['channel_id']),
                    'playable': False,
                })

        channels[:] = sorted(channels, key=_sort_live)

    if len(channels) == 0 and retry:
        logout(delete=False)

        if plugin.logged_in:
            channels = get_replay_channels(addon=addon, retry=False)

    if _debug_mode:
        log.debug('Execution Done: plugin.get_replay_channels')

    return channels

def process_online_search(data):
    if _debug_mode:
        log.debug('Executing: plugin.process_online_search')
        log.debug('Vars: data={data}'.format(data=data))

    items_vod = []
    items_program = []
    vod_links = {}
    moviesseries = settings.getBool('showMoviesSeries')

    if moviesseries:
        vod_data = load_file(file='vod.json', isJSON=True)

        for vod_type in list(vod_data):
            for row in vod_data[vod_type]:
                if not check_key(row, 'id'):
                    continue

                vod_links[row['id']] = {}

                if check_key(row, 'seasons'):
                    vod_links[row['id']]['seasons'] = row['seasons']

                if check_key(row, 'duration'):
                    vod_links[row['id']]['duration'] = row['duration']

                if check_key(row, 'desc'):
                    vod_links[row['id']]['desc'] = row['desc']

    for currow in list(data):
        if currow == "moviesAndSeries":
            if not moviesseries:
                continue

            type = 'vod'
        else:
            type = 'program'

        for row in data[currow]['entries']:
            context = []

            if not check_key(row, 'id') or not check_key(row, 'title'):
                continue

            id = row['id']
            label = row['title']
            channel = ''
            mediatype = ''
            description = ''
            duration = 0
            program_image = ''
            program_image_large = ''

            if check_key(row, 'images'):
                program_image = get_image("boxart", row['images'])
                program_image_large = get_image("HighResLandscape", row['images'])

                if program_image_large == '':
                    program_image_large = program_image
                else:
                    program_image_large += '?w=1920&mode=box'

            playable = False
            path = ''

            if check_key(vod_links, row['id']) and check_key(vod_links[row['id']], 'desc'):
                description = vod_links[row['id']]['desc']

            if type == 'vod':
                label += " (Movies and Series)"
            else:
                label += " (ReplayTV)"

            if check_key(row, 'groupType') and row['groupType'] == 'show':
                if check_key(row, 'episodeMatch') and check_key(row['episodeMatch'], 'seriesEpisodeNumber') and check_key(row['episodeMatch'], 'secondaryTitle'):
                    if len(description) == 0:
                        description += label

                    season = ''

                    if check_key(row, 'seriesNumber'):
                        season = "S" + row['seriesNumber']

                    description += " Episode Match: {season}E{episode} - {secondary}".format(season=season, episode=row['episodeMatch']['seriesEpisodeNumber'], secondary=row['episodeMatch']['secondaryTitle'])

                if type == 'vod':
                    if not check_key(vod_links, row['id']) or not check_key(vod_links[row['id']], 'seasons'):
                        continue

                    context.append((_.ADD_TO_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=add_to_watchlist, id=id, type='group')), ))
                    path = plugin.url_for(func_or_url=vod_series, label=label, description=description, image=program_image, image_large=program_image_large, seasons=json.dumps(vod_links[row['id']]['seasons']), mediagroupid=id)
                else:
                    context.append((_.ADD_TO_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=add_to_watchlist, id=id, type='group')), ))
                    path = plugin.url_for(func_or_url=watchlist_listing, label=label, description=description, image=program_image, image_large=program_image_large, id=id, search=True)
            else:
                context.append((_.ADD_TO_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=add_to_watchlist, id=id, type='group')), ))

                if check_key(row, 'duration'):
                    duration = int(row['duration'])
                elif check_key(row, 'episodeMatch') and check_key(row['episodeMatch'], 'startTime') and check_key(row['episodeMatch'], 'endTime'):
                    duration = int(int(row['episodeMatch']['endTime']) - int(row['episodeMatch']['startTime'])) // 1000
                    id = row['episodeMatch']['id']
                elif check_key(vod_links, row['id']) and check_key(vod_links[row['id']], 'duration'):
                    duration = vod_links[row['id']]['duration']

                path = plugin.url_for(func_or_url=play_video, type=type, channel=channel, id=id, title=None, _is_live=False)
                playable = True
                mediatype = 'video'

            item = plugin.Item(
                label = label,
                info = {
                    'plot': description,
                    'duration': duration,
                    'mediatype': mediatype,
                },
                art = {
                    'thumb': program_image,
                    'fanart': program_image_large
                },
                path = path,
                playable = playable,
                context = context
            )

            if type == "vod":
                items_vod.append(item)
            else:
                items_program.append(item)

    num = min(len(items_program), len(items_vod))
    items = [None]*(num*2)
    items[::2] = items_program[:num]
    items[1::2] = items_vod[:num]
    items.extend(items_program[num:])
    items.extend(items_vod[num:])

    if _debug_mode:
        log.debug('Returned Data: {items}'.format(items=items))
        log.debug('Execution Done: plugin.process_online_search')

    return items

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
        context = []
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
            program_image_large = currow['h'] + '?w=1920&mode=box'
        else:
            program_image_large = program_image

        if check_key(currow, 'c'):
            channel = currow['c']

        context.append((_.ADD_TO_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=add_to_watchlist, id=row, type='item')), ))

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
            path = plugin.url_for(func_or_url=play_video, type='program', channel=channel, id=row, title=None, _is_live=False),
            playable = True,
            context = context
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
        context = []
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
            program_image_large = currow['h'] + '?w=1920&mode=box'
        else:
            program_image_large = program_image

        if check_key(currow, 'c'):
            channel = currow['c']

        context.append((_.ADD_TO_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=add_to_watchlist, id=id, type='item')), ))

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
            path = plugin.url_for(func_or_url=play_video, type='program', channel=channel, id=id, title=None, _is_live=False),
            playable = True,
            context = context
        ))

        item_count = item_count + 1

    returnar = {'items': items, 'totalrows': totalrows, 'count': count}

    if _debug_mode:
        log.debug('Returned Data: {returnar}'.format(returnar=returnar))
        log.debug('Execution Done: plugin.process_replaytv_list_content')

    return returnar

def process_vod_content(data, start=0, series=0, search=None, type=None):
    if _debug_mode:
        log.debug('Executing: plugin.process_vod_content')
        log.debug('Vars: data={data}, start={start}, series={series}, search={search}, type={type}'.format(data=data, start=start, series=series, search=search, type=type))

    start = int(start)
    series = int(series)
    items = []
    count = 0
    item_count = 0

    for row in data:
        context = []
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
        label = currow['title']

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

        if currow['type'] == "show":
            if check_key(currow, 'seasons') and series != 2:
                path = plugin.url_for(func_or_url=vod_series, label=label, description=description, image=program_image, image_large=program_image_large, seasons=json.dumps(currow['seasons']), mediagroupid=id)
                info = {'plot': description}
                playable = False
                context.append((_.ADD_TO_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=add_to_watchlist, id=id, type='group')), ))
            else:
                continue
        else:
            if series != 1:
                path = plugin.url_for(func_or_url=play_video, type='vod', channel=None, id=id, title=None, _is_live=False)
                info = {'plot': description, 'duration': duration, 'mediatype': 'video'}
                playable = True
                context.append((_.ADD_TO_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=add_to_watchlist, id=id, type='group')), ))
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
            context = context
        ))

        item_count += 1

    returnar = {'items': items, 'count': count}

    if _debug_mode:
        log.debug('Returned Data: {returnar}'.format(returnar=returnar))
        log.debug('Execution Done: plugin.process_vod_content')

    return returnar

def process_vod_season(data, title, mediagroupid=None):
    if _debug_mode:
        log.debug('Executing: plugin.process_vod_season')
        log.debug('Vars: data={data}, title={title}, mediagroupid={mediagroupid}'.format(data=data, title=title, mediagroupid=mediagroupid))

    items = []

    if sys.version_info >= (3, 0):
        data['mediaItems'] = list(data['mediaItems'])

    for row in data['mediaItems']:
        context = []
        label = ''
        description = ''
        program_image = ''
        program_image_large = ''
        duration = 0

        if not check_key(row, 'title') or not check_key(row, 'id'):
            continue

        if check_key(row, 'description'):
            description = row['description']

        if check_key(row, 'earliestBroadcastStartTime'):
            startsplit = int(row['earliestBroadcastStartTime']) // 1000

            startT = datetime.datetime.fromtimestamp(startsplit)
            startT = convert_datetime_timezone(startT, "UTC", "UTC")

            if xbmc.getLanguage(xbmc.ISO_639_1) == 'nl':
                label = date_to_nl_dag(startT) + startT.strftime(" %d ") + date_to_nl_maand(startT) + startT.strftime(" %Y %H:%M ") + row['title']
            else:
                label = (startT.strftime("%A %d %B %Y %H:%M ") + row['title']).capitalize()
        else:
            label = row['title']

        if check_key(row, 'duration'):
            duration = int(row['duration'])

        if check_key(row, 'images'):
            program_image = get_image("boxart", row['images'])
            program_image_large = get_image("HighResLandscape", row['images'])

            if program_image_large == '':
                program_image_large = program_image
            else:
                program_image_large += '?w=1920&mode=box'

        if mediagroupid:
            context.append((_.ADD_TO_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=add_to_watchlist, id=mediagroupid, type='group')), ))

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
            path = plugin.url_for(func_or_url=play_video, type='vod', channel=None, id=row['id'], title=title, _is_live=False),
            playable = True,
            context = context
        ))

    if _debug_mode:
        log.debug('Returned Data: {items}'.format(items=items))
        log.debug('Execution Done: plugin.process_vod_season')

    return items

def process_watchlist(data):
    if _debug_mode:
        log.debug('Executing: plugin.process_watchlist')
        log.debug('Vars: data={data}'.format(data=data))

    items = []

    for row in data['entries']:
        context = []

        if check_key(row, 'mediaGroup') and check_key(row['mediaGroup'], 'medium') and check_key(row['mediaGroup'], 'id'):
            currow = row['mediaGroup']
            id = currow['id']
        elif check_key(row, 'mediaItem') and check_key(row['mediaItem'], 'medium') and check_key(row['mediaItem'], 'mediaGroupId'):
            currow = row['mediaItem']
            id = currow['mediaGroupId']
        else:
            continue

        if not check_key(currow, 'title'):
            continue

        context.append((_.REMOVE_FROM_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=remove_from_watchlist, id=id)), ))

        if check_key(currow, 'isReplayTv') and currow['isReplayTv'] == "false":
            if not settings.getBool('showMoviesSeries'):
                continue

            type = 'vod'
        else:
            type = 'program'

        channel = ''
        mediatype = ''
        duration = ''
        description = ''
        program_image = ''
        program_image_large = ''
        playable = False
        path = ''

        if check_key(currow, 'description'):
            description = currow['description']

        if check_key(currow, 'images'):
            program_image = get_image("boxart", currow['images'])
            program_image_large = get_image("HighResLandscape", currow['images'])

            if program_image_large == '':
                program_image_large = program_image
            else:
                program_image_large += '?w=1920&mode=box'

        if currow['medium'] == 'TV':
            if not check_key(currow, 'seriesLinks'):
                path = plugin.url_for(func_or_url=watchlist_listing, label=currow['title'], description=description, image=program_image, image_large=program_image_large, id=id, search=False)
            else:
                path = plugin.url_for(func_or_url=vod_series, label=currow['title'], description=description, image=program_image, image_large=program_image_large, seasons=json.dumps(currow['seriesLinks']))
        elif currow['medium'] == 'Movie':
            if check_key(currow, 'duration'):
                duration = int(currow['duration'])
            elif check_key(currow, 'startTime') and check_key(currow, 'endTime'):
                duration = int(int(currow['endTime']) - int(currow['startTime'])) // 1000
            else:
                duration = 0

            path = plugin.url_for(func_or_url=play_video, type=type, channel=channel, id=currow['id'], title=None, _is_live=False)
            playable = True
            mediatype = 'video'

        items.append(plugin.Item(
            label = currow['title'],
            info = {
                'plot': description,
                'duration': duration,
                'mediatype': mediatype,
            },
            art = {
                'thumb': program_image,
                'fanart': program_image_large
            },
            path = path,
            playable = playable,
            context = context
        ))

    if _debug_mode:
        log.debug('Returned Data: {items}'.format(items=items))
        log.debug('Execution Done: plugin.process_watchlist')

    return items

def process_watchlist_listing(data, id=None):
    if _debug_mode:
        log.debug('Executing: plugin.process_watchlist_listing')
        log.debug('Vars: data={data}, id={id}'.format(data=data, id=id))

    items = []

    channeldata = {}
    stations = load_file(file='channels.json', isJSON=True)

    if stations:
        for row in stations:
            channeldata[row['stationSchedules'][0]['station']['id']] = row['stationSchedules'][0]['station']['title']

    for row in data['listings']:
        context = []

        if not check_key(row, 'program'):
            continue

        currow = row['program']

        if not check_key(currow, 'title') or not check_key(row, 'id'):
            continue

        duration = 0

        if check_key(row, 'endTime') and check_key(row, 'startTime'):
            startsplit = int(row['startTime']) // 1000
            endsplit = int(row['endTime']) // 1000
            duration = endsplit - startsplit

            startT = datetime.datetime.fromtimestamp(startsplit)
            startT = convert_datetime_timezone(startT, "UTC", "UTC")
            endT = datetime.datetime.fromtimestamp(endsplit)
            endT = convert_datetime_timezone(endT, "UTC", "UTC")

            if endT < (datetime.datetime.now(pytz.timezone("UTC")) - datetime.timedelta(days=7)):
                continue

            if xbmc.getLanguage(xbmc.ISO_639_1) == 'nl':
                label = '{weekday} {day} {month} {yearhourminute} '.format(weekday=date_to_nl_dag(startT), day=startT.strftime("%d"), month=date_to_nl_maand(startT), yearhourminute=startT.strftime("%Y %H:%M"))
            else:
                label = startT.strftime("%A %d %B %Y %H:%M ").capitalize()

            label += currow['title']
        else:
            label = currow['title']

        if check_key(channeldata, row['stationId']):
            label += ' ({station})'.format(station=channeldata[row['stationId']])

        if id:
            context.append((_.ADD_TO_WATCHLIST, 'RunPlugin({context_url})'.format(context_url=plugin.url_for(func_or_url=add_to_watchlist, id=id, type="group")), ))

        channel = ''
        description = ''
        program_image = ''
        program_image_large = ''

        if check_key(currow, 'description'):
            description = currow['description']

        if check_key(currow, 'duration'):
            duration = int(currow['duration'])

        if check_key(currow, 'images'):
            program_image = get_image("boxart", currow['images'])
            program_image_large = get_image("HighResLandscape", currow['images'])

            if program_image_large == '':
                program_image_large = program_image
            else:
                program_image_large += '?w=1920&mode=box'

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
            path = plugin.url_for(func_or_url=play_video, type="program", channel=channel, id=row['id'], title=None, _is_live=False),
            playable = True,
            context = context
        ))

    if _debug_mode:
        log.debug('Returned Data: {items}'.format(items=items))
        log.debug('Execution Done: plugin.process_watchlist_listing')

    return items

def _sort_live(element):
    return element['chno']

def _sort_replay_items(element):
    return element.get_li().getProperty('fuzz_total')