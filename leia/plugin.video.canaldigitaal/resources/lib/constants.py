CONST_BASE_URL = 'https://livetv.canaldigitaal.nl'
CONST_DEFAULT_API = 'https://tvapi.solocoo.tv/v1'
CONST_LOGIN_URL = 'https://login.canaldigitaal.nl'

CONST_LOGIN_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Upgrade-Insecure-Requests': '1',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
    'DNT': '1',
    'Origin': CONST_LOGIN_URL,
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-User': '?1',
    'Sec-Fetch-Dest': 'document',
    'Accept-Encoding': 'deflate, br',
    'Accept-Language': 'en-US,en;q: 0.9,nl;q: 0.8',
    'Content-Type': 'application/x-www-form-urlencoded',
}

CONST_BASE_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Connection': 'keep-alive',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
    'DNT': '1',
    'Origin': CONST_BASE_URL,
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Dest': 'empty',
    'Referer': CONST_BASE_URL + '/',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q: 0.9,nl;q: 0.8',
}

CONST_EPG = 'https://dut-epg.github.io/c.epg.db.zip'
CONST_IMAGES = 'https://dut-epg.github.io/c.images.zip'
CONST_MD5 = 'https://dut-epg.github.io/c.md5.json'
CONST_MINIMALEPG = 'https://dut-epg.github.io/c.epg.db.minimal.zip'
CONST_RADIO = 'https://dut-epg.github.io/radio.m3u8'
CONST_SETTINGS = 'https://dut-epg.github.io/c.settings.json'

SETUP_DB_QUERIES = [
    '''CREATE TABLE IF NOT EXISTS `vars` (
        `profile_id` INT(11) PRIMARY KEY,
        `arch` VARCHAR(255) DEFAULT '',
        `browser_name` VARCHAR(255) DEFAULT '',
        `browser_version` VARCHAR(255) DEFAULT '',
        `cookies` TEXT DEFAULT '',
        `devicekey` VARCHAR(255) DEFAULT '',
        `epg_md5` VARCHAR(255) DEFAULT '',
        `epgrun` TINYINT(1) DEFAULT 0,
        `epgruntime` INT(11) DEFAULT 0,
        `first_boot` TINYINT(1) DEFAULT 1,
        `images_md5` VARCHAR(255) DEFAULT '',
        `img_size` VARCHAR(255) DEFAULT '',
        `last_login_success` TINYINT(1) DEFAULT 0,
        `last_playing` INT(11) DEFAULT 0,
        `last_tested` VARCHAR(255) DEFAULT '',
        `os_name` VARCHAR(255) DEFAULT '',
        `os_version` VARCHAR(255) DEFAULT '',
        `proxyserver_port` INT(11) DEFAULT 0,
        `pswd` VARCHAR(255) DEFAULT '',
        `search1` VARCHAR(255) DEFAULT '',
        `search2` VARCHAR(255) DEFAULT '',
        `search3` VARCHAR(255) DEFAULT '',
        `search4` VARCHAR(255) DEFAULT '',
        `search5` VARCHAR(255) DEFAULT '',
        `search6` VARCHAR(255) DEFAULT '',
        `search7` VARCHAR(255) DEFAULT '',
        `search8` VARCHAR(255) DEFAULT '',
        `search9` VARCHAR(255) DEFAULT '',
        `search10` VARCHAR(255) DEFAULT '',
        `session_token` VARCHAR(255) DEFAULT '',
        `stream_duration` INT(11) DEFAULT 0,
        `stream_hostname` VARCHAR(255) DEFAULT '',
        `system` VARCHAR(255) DEFAULT '',
        `test_running` TINYINT(1) DEFAULT 0,
        `user_agent` VARCHAR(255) DEFAULT '',
        `username` VARCHAR(255) DEFAULT '',
        `vod_md5` VARCHAR(255) DEFAULT ''
    )''',
]