CONST_BASE_URL = 'https://t-mobiletv.nl'

CONST_BASE_HEADERS = {
    'Accept': '*/*',
    'Accept-Language': 'nl',
    'Cache-Control': 'no-cache',
    'DNT': '1',
    'Origin': CONST_BASE_URL,
    'Pragma': 'no-cache',
    'Referer': CONST_BASE_URL + '/inloggen/index.html',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}

CONST_EPG = 'https://dut-epg.github.io/t.epg.xml.zip'
CONST_IMAGES = 'https://dut-epg.github.io/t.images.zip'
CONST_MD5 = 'https://dut-epg.github.io/t.md5.json'
CONST_MINIMALEPG = 'https://dut-epg.github.io/t.epg.xml.zip'
CONST_RADIO = 'https://dut-epg.github.io/radio.m3u8'
CONST_SETTINGS = 'https://dut-epg.github.io/t.settings.json'
CONST_VOD = 'https://dut-epg.github.io/t.vod.json'