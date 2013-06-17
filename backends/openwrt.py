import contextlib
import os
import shutil
import subprocess

import abstract
from utils import ssh

class OpenwrtBackend(abstract.AbstractBackend):
    def __init__(self, hostname, settings):
        super(OpenwrtBackend, self).__init__(hostname, settings)
        self.host = hostname
        self.settings = settings
        self.password = settings.pop('password', None)

    def get_config(self):
        self.session = ssh.SSHSession(
                ssh.gen_args(self.host, self.settings),
                password=self.password
        )

        with contextlib.closing(self.session):
            backup_cmd = 'sysupgrade  -b -'
            backup_hex = self.session.call(backup_cmd + " | hexdump -v -e '1/1 \"%02x\"'")

            if len(backup_hex) % 2:
                raise RuntimeError("Unexpected format for hexdump")

            tarball = bytes()
            while backup_hex:
                tarball += chr(int(backup_hex[:2],16))
                backup_hex = backup_hex[2:]
            return tarball

    def store_config(self, config, path):
        if os.path.exists(path):
            shutil.rmtree(path)

        os.mkdir(path)
        tar = subprocess.Popen(['tar', '-xz', '-C', path], stdin=subprocess.PIPE)
        tar.communicate(config)
        if tar.returncode != 0:
            raise RuntimeError("Couldn't store config.")
