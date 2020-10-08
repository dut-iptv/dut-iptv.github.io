import json, xbmcaddon

from resources.lib.base.constants import ADDON_ID

try:
    unicode
except NameError:
    unicode = str

def open():
    xbmcaddon.Addon(ADDON_ID).openSettings()

def getDict(key, default=None):
    try:
        return json.loads(get(key))
    except:
        return default

def setDict(key, value):
    set(key, json.dumps(value))

def getInt(key, default=None):
    try:
        return int(get(key))
    except:
        return default

def setInt(key, value):
    set(key, int(value))

def getBool(key, default=False):
    value = get(key).lower()
    if not value:
        return default
    else:
        return value == 'true'

def getEnum(key, choices=None, default=None):
    index = getInt(key)
    if index == None or not choices:
        return default

    try:
        return choices[index]
    except KeyError:
        return default

def remove(key):
    set(key, '')

def setBool(key, value=True):
    set(key, 'true' if value else 'false')

def get(key, default=''):
    return unicode(xbmcaddon.Addon(ADDON_ID).getSetting(key)) or unicode(default)

def set(key, value=''):
    xbmcaddon.Addon(ADDON_ID).setSetting(key, str(value))

FRESH = getBool('_fresh', True)
if FRESH:
    setBool('_fresh', False)