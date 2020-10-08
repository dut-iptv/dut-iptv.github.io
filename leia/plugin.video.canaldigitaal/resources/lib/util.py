from resources.lib.base import uaparser
from resources.lib.base.util import load_profile, query_settings

def update_settings():
    profile_settings = load_profile(profile_id=1)

    user_agent = profile_settings['user_agent']
    browser_name = uaparser.detect(user_agent)['browser']['name']
    browser_version = uaparser.detect(user_agent)['browser']['version']
    os_name = uaparser.detect(user_agent)['os']['name']
    os_version = uaparser.detect(user_agent)['os']['version']

    query = "UPDATE `vars` SET `browser_name`='{browser_name}', `browser_version`='{browser_version}', `os_name`='{os_name}', `os_version`='{os_version}' WHERE profile_id={profile_id}".format(browser_name=browser_name, browser_version=browser_version, os_name=os_name, os_version=os_version, profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)