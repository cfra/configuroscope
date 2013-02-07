class AbstractNotifier(object):
    def __init__(self, hostname, settings):
        pass
    def notify(self, success):
        raise NotImplementedError
