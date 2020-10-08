from resources.lib.base.language import _

class Exit(Exception):
    pass

class Error(Exception):
    message = _.NO_ERROR_MSG
    heading = None

    def __init__(self, message=None, heading=None):
        super(Error, self).__init__(message or self.message)
        self.heading = heading or self.heading

class InputStreamError(Error):
    pass

class PluginError(Error):
    pass

class RouterError(Error):
    pass