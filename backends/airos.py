import contextlib

import abstract
from utils import ssh

class AirOSBackend(abstract.AbstractBackend):
    def __init__(self, hostname, settings):
        super(AirOSBackend, self).__init__(hostname, settings)
        self.host = hostname
        self.settings = settings
        self.password = settings.pop('password', None)

    def get_config(self):
        self.session = ssh.SSHSession(
                ssh.gen_args(self.host, self.settings),
                password=self.password
        )

        with contextlib.closing(self.session):
            return self.session.call("cat /tmp/system.cfg")
