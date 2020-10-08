import time, xbmc, xbmcaddon, xbmcgui

from resources.lib.api import API
from resources.lib.base import settings
from resources.lib.base.constants import ADDON_PROFILE
from resources.lib.base.util import change_icon, check_iptv_link, clear_cache, download_files, find_free_port, get_system_arch
from resources.lib.proxy import HTTPMonitor, RemoteControlBrowserService

api = API()

def daily():
    check_iptv_link()
    clear_cache()

def hourly(type=0):
    if type < 2:
        download_files()

    if type > 0:
        if api.test_channels(tested=False) < 5:
            api.test_channels(tested=True)

def startup():
    settings.setBool(key='_test_running', value=False)
    system, arch = get_system_arch()
    settings.set(key="_system", value=system)
    settings.set(key="_arch", value=arch)

    settings.setInt(key='_proxyserver_port', value=find_free_port())

    channels = False

    if settings.getInt(key='_channels_age') < int(time.time() - 86400):
        channels = True

    api.new_session(force=False, retry=False, channels=channels)
    api.update_prefs()

    hourly(type=0)
    daily()
    change_icon()
    hourly(type=2)

def main():
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