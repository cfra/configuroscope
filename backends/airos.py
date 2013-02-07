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
            cmd = 'echo "---BEGIN CONFIG---" && cat /tmp/system.cfg && echo "---END CONFIG---"'
            config = self.session.call(cmd)

            begin = "\n---BEGIN CONFIG---\n"
            end = "\n---END CONFIG---\n"
            index = config.find(begin)
            if index < 0:
                raise RuntimeError("Could not parse output")
            config = config[index + len(begin):]
            index = config.find(end)
            if index < 0:
                raise RuntimeError("Could not parse output")
            config = config[:index+1]
            return config
