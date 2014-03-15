import contextlib
import pexpect
import tempfile

import abstract
from utils import ssh
from utils import timeout

class SFTPBackend(abstract.AbstractBackend):
    def __init__(self, hostname, settings):
        super(SFTPBackend, self).__init__(hostname, settings)
        self.host = hostname
        self.settings = settings
        self.password = settings.pop('password', None)

    def get_config(self):
        target_file = tempfile.NamedTemporaryFile()
        with contextlib.closing(target_file):
            self.download_config(target_file)

            with open(target_file.name, 'r') as config_file:
                return config_file.read()

    def download_config(self, target_file):
        if 'user' in self.settings:
            hostpart = '%s@%s' % (self.settings['user'], self.host)
        else:
            hostpart = self.host

        sftp_args = [
                'sftp',
                '%s:%s' % (hostpart, self.settings['path']),
                target_file.name
        ]

        session = ssh.SSHSession(
                sftp_args, password=self.password,
                prompt=pexpect.EOF,
        )

        if session.isalive():
            with timeout.timeout(5000):
                try:
                    session.wait()
                except pexpect.ExceptionPexpect:
                    if session.isalive():
                        raise

        if session.exitstatus != 0:
            raise RuntimeError(
                    "SFTP process did not terminate successfuly. Exitcode: %d" % session.exitstatus)
