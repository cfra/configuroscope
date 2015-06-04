import contextlib

import abstract
from utils import ssh

class JunosBackend(abstract.AbstractBackend):
    def __init__(self, hostname, settings):
        super(JunosBackend, self).__init__(hostname, settings)
        self.host = hostname
        self.settings = settings
        self.password = settings.pop('password', None)

    def get_config(self):
        self.session = ssh.SSHSession(
                ssh.gen_args(self.host, self.settings),
                password=self.password,
                prompt='\S+@\S+> '
        )

        with contextlib.closing(self.session):
            self.session.call("set cli screen-width 0", frame=False)
            self.session.call("set cli screen-length 0", frame=False)
            config = self.session.call("show configuration", frame=False)

        return config
