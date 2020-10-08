import sys

from resources.lib.base import signals
from resources.lib.base.constants import ADDON_ID
from resources.lib.base.exceptions import RouterError
from resources.lib.base.language import _
from resources.lib.base.log import log

try:
    unicode
except NameError:
    unicode = str

try:
    from urllib.parse import parse_qsl, urlencode, unquote
except ImportError:
    from urlparse import parse_qsl, unquote
    from urllib import urlencode

_routes = {}

# @router.add('_settings', settings)
def add(url, f):
    if url == None:
        url = f.__name__
    _routes[url] = f

# @router.route('_settings')
def route(url):
    def decorator(f):
        add(url, f)
        return f
    return decorator

# @router.parse_url('?_=_settings')
def parse_url(url):
    if url.startswith('?'):
        params = dict(parse_qsl(url.lstrip('?'), keep_blank_values=True))
        for key in params:
            params[key] = unquote(params[key])

        _url = params.pop('_', '')
    else:
        params = {}
        _url = url

    params['_url'] = url

    function = _routes.get(_url)

    if not function:
        raise RouterError(_(_.ROUTER_NO_FUNCTION, raw_url=url, parsed_url=_url))

    log.debug('Router Parsed: \'{0}\' => {1} {2}'.format(url, function.__name__, params))

    return function, params

def url_for_func(func, **kwargs):
    for url in _routes:
        if _routes[url].__name__ == func.__name__:
            return build_url(url, **kwargs)

    raise RouterError(_(_.ROUTER_NO_URL, function_name=func.__name__))

def url_for(func_or_url, **kwargs):
    if callable(func_or_url):
        return url_for_func(func_or_url, **kwargs)
    else:
        return build_url(func_or_url, **kwargs)

def build_url(url, addon_id=ADDON_ID, **kwargs):
    kwargs['_'] = url
    is_live = kwargs.pop('_is_live', False)

    params = []
    for k in sorted(kwargs):
        if kwargs[k] == None:
            continue

        try: params.append((k, str(kwargs[k]).encode('utf-8')))
        except: params.append((k, kwargs[k]))

    if is_live:
        params.append(('_l', '.pvr'))

    return 'plugin://{0}/?{1}'.format(addon_id, urlencode(encode_obj(params)))

# router.dispatch('?_=_settings')
def dispatch(url):
    with signals.throwable():
        function, params = parse_url(url)
        signals.emit(signals.BEFORE_DISPATCH)

        function(**params)

    signals.emit(signals.AFTER_DISPATCH)

def encode_obj(in_obj):

    def encode_list(in_list):
        out_list = []
        for el in in_list:
            out_list.append(encode_obj(el))
        return out_list

    def encode_dict(in_dict):
        out_dict = {}

        if sys.version_info < (3, 0):
            for k, v in in_dict.iteritems():
                out_dict[k] = encode_obj(v)
        else:
            for k, v in in_dict.items():
                out_dict[k] = encode_obj(v)

        return out_dict

    if isinstance(in_obj, unicode):
        return in_obj.encode('utf-8')
    elif isinstance(in_obj, list):
        return encode_list(in_obj)
    elif isinstance(in_obj, tuple):
        return tuple(encode_list(in_obj))
    elif isinstance(in_obj, dict):
        return encode_dict(in_obj)

    return in_obj