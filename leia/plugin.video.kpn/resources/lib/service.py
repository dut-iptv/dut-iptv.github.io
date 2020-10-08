import time, xbmc

from resources.lib.api import API
from resources.lib.base.constants import ADDON_PROFILE
from resources.lib.base.log import log
from resources.lib.base.util import change_icon, check_iptv_link, clear_cache, download_files, find_free_port, get_system_arch, is_file_older_than_x_days, query_settings, update_prefs
from resources.lib.proxy import HTTPMonitor, RemoteControlBrowserService
from resources.lib.util import update_settings

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

def daily():
    update_settings()
    check_iptv_link()
    clear_cache()

    vod_subscription_file = ADDON_PROFILE + 'vod_subscription.json'

    if is_file_older_than_x_days(vod_subscription_file, days=1):
        api.vod_subscription()

def hourly(type=0):
    if type < 2:
        download_files()

    #if type > 0:
    #    if api.test_channels(tested=False) < 5:
    #        api.test_channels(tested=True)

def startup():
    system, arch = get_system_arch()
    proxyserver_port = find_free_port()

    query = "UPDATE `vars` SET `arch`='{arch}', `system`='{system}', `test_running`=0, `proxyserver_port`={proxyserver_port} WHERE profile_id={profile_id}".format(arch=arch, system=system, proxyserver_port=proxyserver_port, profile_id=1)
    query_settings(query=query, return_result=False, return_insert=False, commit=True)

    hourly(type=0)
    daily()
    change_icon()

    update_prefs()

    hourly(type=2)

def main():
    try:
        startup()
        service = RemoteControlBrowserService()
        service.clearBrowserLock()
        monitor = HTTPMonitor(service)
        service.reloadHTTPServer()

        k = 0
        z = 0
        l = 0

        while not xbmc.Monitor().abortRequested():
            if xbmc.Monitor().waitForAbort(1):
                api._abortRequested = True
                break

            if k == 60:
                k = 0
                z += 1

            if z == 60:
                z = 0
                l += 1

                hourly(type=1)

            if l == 24:
                l = 0

                daily()

            k += 1

        api._abortRequested = True
        service.shutdownHTTPServer()
    except RuntimeError:
        pass