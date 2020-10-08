from resources.lib.base import uaparser
from resources.lib.base.util import load_file, load_profile, query_settings
from resources.lib.constants import CONST_DEFAULT_API, CONST_DEFAULT_IMG_SIZE

try:
    from sqlite3 import dbapi2 as sqlite
except:
    from pysqlite2 import dbapi2 as sqlite

def update_settings():
    profile_settings = load_profile(profile_id=1)
    settingsJSON = load_file(file='settings.json', isJSON=True)

    try:
        api_url = settingsJSON['api_url']

        if len(api_url) == 0:
            api_url = CONST_DEFAULT_API
    except:
        api_url = CONST_DEFAULT_API

    try:
        img_size = settingsJSON['img_size']

        if len(img_size) == 0:
            img_size = CONST_DEFAULT_IMG_SIZE
    except:
        img_size = CONST_DEFAULT_IMG_SIZE

    user_agent = profile_settings['user_agent']
    browser_name = uaparser.detect(user_agent)['browser']['name']
    browser_version = uaparser.detect(user_agent)['browser']['version']
    os_name = uaparser.detect(user_agent)['os']['name']
    os_version = uaparser.detect(user_agent)['os']['version']

    query = "UPDATE `vars` SET `api_url`='{api_url}', `img_size`='{img_size}', `browser_name`='{browser_name}', `browser_version`='{browser_version}', `os_name`='{os_name}', `os_version`='{os_version}' WHERE profile_id={profile_id}".format(api_url=api_url, img_size=img_size, browser_name=browser_name, browser_version=browser_version, os_name=os_name, os_version=os_version, profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)