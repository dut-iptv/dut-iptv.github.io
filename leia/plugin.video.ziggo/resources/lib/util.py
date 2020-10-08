import re

from resources.lib.base import settings
from resources.lib.base.util import check_key, load_file
from resources.lib.constants import CONST_DEFAULT_CLIENTID

def get_image(prefix, content):
    best_image = 0
    image_url = ''

    for images in content:
        if prefix in images['assetTypes']:
            if best_image < 7:
                best_image = 7
                image_url = images['url']
        elif ('HighResPortrait') in images['assetTypes']:
            if best_image < 6:
                best_image = 6
                image_url = images['url']
        elif ('HighResLandscapeShowcard') in images['assetTypes']:
            if best_image < 5:
                best_image = 5
                image_url = images['url']
        elif ('HighResLandscape') in images['assetTypes']:
            if best_image < 4:
                best_image = 4
                image_url = images['url']
        elif (prefix + '-xlarge') in images['assetTypes']:
            if best_image < 3:
                best_image = 3
                image_url = images['url']
        elif (prefix + '-large') in images['assetTypes']:
            if best_image < 2:
                best_image = 2
                image_url = images['url']
        elif (prefix + '-medium') in images['assetTypes']:
            if best_image < 1:
                best_image = 1
                image_url = images['url']

    return image_url

def get_play_url(content):
    if settings.getBool(key='_base_v3') and check_key(content, 'url') and check_key(content, 'contentLocator'):
        return {'play_url': content['url'], 'locator': content['contentLocator']}
    else:
        for stream in content:
            if  'streamingUrl' in stream and 'contentLocator' in stream and 'assetTypes' in stream and 'Orion-DASH' in stream['assetTypes']:
                return {'play_url': stream['streamingUrl'], 'locator': stream['contentLocator']}

    return {'play_url': '', 'locator': ''}

def remove_ac3(xml):
    try:
        result = re.findall(r'<AdaptationSet(?:(?!</AdaptationSet>)[\S\s])+</AdaptationSet>', xml)

        for match in result:
            if "codecs=\"ac-3\"" in match:
                xml = xml.replace(match, "")
    except:
        pass

    return xml

def update_settings():
    settingsJSON = load_file(file='settings.json', isJSON=True)

    try:
        base = settingsJSON['settings']['urls']['base']

        if settings.getBool(key='_base_v3'):
            basethree = settingsJSON['settings']['urls']['alternativeAjaxBase']
        else:
            basethree = base

        complete_base_url = '{base_url}/{country_code}/{language_code}'.format(base_url=basethree, country_code=settingsJSON['settings']['countryCode'], language_code=settingsJSON['settings']['languageCode'])

        settings.set(key='_base_url', value=complete_base_url + '/web')
        settings.set(key='_search_url', value=settingsJSON['settings']['routes']['search'].replace(base, basethree))
        settings.set(key='_session_url', value=settingsJSON['settings']['routes']['session'].replace(base, basethree))
        #settings.set(key='_token_url', value=settingsJSON['settings']['routes']['refreshToken'].replace(base, basethree))
        settings.set(key='_channels_url', value=settingsJSON['settings']['routes']['channels'].replace(base, basethree))
        settings.set(key='_token_url',  value='{complete_base_url}/web/license/token'.format(complete_base_url=complete_base_url))
        settings.set(key='_widevine_url', value='{complete_base_url}/web/license/eme'.format(complete_base_url=complete_base_url))
        settings.set(key='_listings_url', value=settingsJSON['settings']['routes']['listings'].replace(base, basethree))
        settings.set(key='_mediaitems_url', value=settingsJSON['settings']['routes']['mediaitems'].replace(base, basethree))
        settings.set(key='_mediagroupsfeeds_url', value=settingsJSON['settings']['routes']['mediagroupsfeeds'].replace(base, basethree))
        settings.set(key='_watchlist_url', value=settingsJSON['settings']['routes']['watchlist'].replace(base, basethree))
    except:
        pass

    try:
        client_id = settingsJSON['client_id']
    except:
        client_id = CONST_DEFAULT_CLIENTID

    settings.set(key='_client_id', value=client_id)