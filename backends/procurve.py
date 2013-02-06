import contextlib
import pexpect

import abstract
from utils import vt100dropper

class HPSession(pexpect.spawn):
    """A pexpect session for HP Networking Switches.
    It uses a tool called vt100dropper to get rid of most of the
    weird escape sequences this switch uses"""

    anchor = r'(?:^|[\r\n])'
    prompt = anchor + r'(?P<host>\S*)(?P<mode>[#>]) '

    def __init__(self, args, **kwargs):
        password = kwargs.pop('password', None)

        pexpect.spawn.__init__(
                self, vt100dropper.path,
                [ vt100dropper.path ] + args,
                **kwargs)

        stage = -1
        while True:
            index = self.expect([
                r'[pP]assword:',
                'Press any key to continue',
                self.prompt,
            ])
            if index <= stage:
                raise RuntimeError("No progress in login process.")
            stage = index
            if index == 0:
                if password is None:
                    raise RuntimeError("Password required but not given")
                self.sendline(password)
            elif index == 1:
                self.sendline('')
            else:
                # Login complete
                break

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
        self.host = hostname
        self.password = settings.pop('password', None)
        self.protocol = settings.pop('protocol', 'SSH')

    def get_config(self):
        if self.protocol == 'SSHv1':
            self.session = HPSession(['ssh', '-1', self.host], password=self.password)
        elif self.protocol == 'SSH':
            self.session = HPSession(['ssh', self.host], password=self.password)
        else:
            raise RuntimeError("Telnet not supported, sorry")

        with contextlib.closing(self.session):
            config = self.session.call('show running-config')
            config_pattern = 'Running configuration:\n\n'
            offset = config.find(config_pattern)
            if offset < 0:
                raise RuntimeError("Ununderstood failure getting config. Sorry.")
            config = config[offset + len(config_pattern):]
            return config
