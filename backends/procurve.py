import contextlib
import pexpect

import abstract
from utils import ssh
from utils import vt100dropper

class HPSession(ssh.SSHSession):
    """A pexpect session for HP Networking Switches.
    It uses a tool called vt100dropper to get rid of most of the
    weird escape sequences this switch uses"""

    prompt = ssh.SSHSession.anchor + r'(?P<host>\S*)(?P<mode>[#>]) '

    def __init__(self, args, **kwargs):
        password = kwargs.pop('password', None)

        pexpect.spawn.__init__(
                self, vt100dropper.path,
                [ vt100dropper.path ] + args,
                **kwargs)

        rv = self.ssh_login(password, [
            'Press any key to continue',
            self.prompt,
        ])
        if rv == 0:
            self.sendline('')
            self.expect(self.prompt)
        # We got a prompt, login complete

    def call(self, command):
        self.sendline(command)
        answer = ''
        while True:
            # Handle output paging
            ret = self.expect([self.prompt, self.anchor + r'-- MORE --.*Control-C',
                                self.anchor + 'Invalid input:'])
            if ret == 2:
                # An error occured. Expect the next prompt and raise an exception
                self.expect(self.prompt)
                raise RuntimeError('Invalid command: %r' % self.before)
            answer += self.before
            if ret == 1:
                # Answer has been paged. Request another page
                self.send(' ')
            else:
                # Prompt has reappeared. We are done :)
                break

        # Clean up the answer
        answer = answer.replace('\n\r','\n')
        return answer

class ProcurveBackend(abstract.AbstractBackend):
    def __init__(self, hostname, settings):
        super(ProcurveBackend, self).__init__(hostname, settings)
        self.host = hostname
        self.settings = settings
        self.password = settings.pop('password', None)

    def get_config(self):
        self.session = HPSession(
                ssh.gen_args(self.host, self.settings),
                password = self.password
        )

        with contextlib.closing(self.session):
            config = self.session.call('show running-config')
            config_pattern = 'Running configuration:\n\n'
            offset = config.find(config_pattern)
            if offset < 0:
                raise RuntimeError("Ununderstood failure getting config. Sorry.")
            config = config[offset + len(config_pattern):]
            return config
