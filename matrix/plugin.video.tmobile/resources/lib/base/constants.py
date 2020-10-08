import sys, xbmc, xbmcaddon

##### ADDON ####
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')

ADDON_PATH = xbmc.translatePath(ADDON.getAddonInfo('path'))
ADDON_PROFILE = xbmc.translatePath(ADDON.getAddonInfo('profile'))

if sys.version_info < (3, 0):
    ADDON_PATH = ADDON_PATH.decode("utf-8")
    ADDON_PROFILE = ADDON_PROFILE.decode("utf-8")

ADDON_ICON = ADDON.getAddonInfo('icon')
ADDON_FANART = ADDON.getAddonInfo('fanart')
#################

DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36'

#### SESSION ####
SESSION_CHUNKSIZE = 4096
#################