import pexpect
import sys

import settings

class SSHSession(pexpect.spawn):
    """A pexpect session for AirOS Devices"""

    anchor = r'(?:^|[\r\n])'
    prompt = anchor + r'[^=\r\n]*# '

    def __init__(self, args, **kwargs):
        password = kwargs.pop('password', None)
        prompt = kwargs.pop('prompt', None)

        if prompt is not None:
            if prompt is pexpect.EOF:
                self.prompt = pexpect.EOF
            else:
                self.prompt = self.anchor + prompt

        pexpect.spawn.__init__(self, args[0], args[1:], **kwargs)
        if 'debug' in dir(settings):
            if settings.debug:
                self.logfile = sys.stderr

        rv = self.ssh_login(password, [
            self.prompt,
        ])
        # We got a prompt, login complete

    def call(self, command, frame=True):
        if frame:
            command_line = 'echo "---BEGIN COMMAND---" && ('
            command_line += command + ') && '
            command_line += 'echo "---END COMMAND---"'
        else:
            command_line = command

        self.sendline(command_line)
        self.expect(self.prompt)

        answer = self.before
        answer = answer.replace('\r\n', '\n')
        answer = answer.replace('\r', '\n')

        if not frame:
            return answer

        begin = "\n---BEGIN COMMAND---\n"
        end = "---END COMMAND---\n"
        index = answer.find(begin)
        if index < 0:
            raise RuntimeError("Could not parse frame")
        answer = answer[index + len(begin):]
        index = answer.find(end)
        if index < 0:
            raise RuntimeError("Could not parse frame")
        answer = answer[:index]

        return answer

    def ssh_login(self, password, patterns):
        """Handle SSH login to remote Host.

        The caller should provide a list of patterns on which he
        wishes us to pass him back control. When we do so, we will
        return the index of his pattern which matched."""

        stage = -1
        while True:
            index = self.expect([
                'Are you sure you want to continue connecting (yes/no)?',
                r'[pP]assword:'] + patterns);
            if index <= stage:
                raise RuntimeError("No progress in login process.")
            stage = index
            if index == 0:
                # Accept new keys by default
                self.sendline('yes')
            elif index == 1:
                if password is None:
                    raise RuntimeError("Password required but not given")
                self.sendline(password)
            else:
                # User pattern matched, pass back control
                return index - 2

def gen_args(hostname, settings):
    """Generate a call to OpenSSH client based on the given settings"""

    args = ['ssh']
    if 'protocol' in settings and settings['protocol']  == 'SSHv1':
        args += ['-1']
    if 'user' in settings:
        args += ['-l', settings['user']]
    args += [hostname]
    return args
