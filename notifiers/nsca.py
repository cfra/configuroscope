import subprocess

import abstract
import settings

class NSCANotifier(abstract.AbstractNotifier):
    def __init__(self, hostname, settings):
        super(NSCANotifier, self).__init__(hostname, settings)

        self.hostname = hostname
        self.settings = settings

    def notify(self, success):
        nsca_send = subprocess.Popen(settings.send_nsca_args, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        nsca_message = '%s\t%s\t%s\t%s\n' % (
                self.settings['nsca_hostname'],
                self.settings['nsca_servicedesc'],
                '0' if success else '2',
                'Config Fetched' if success else 'Config couldn\'t be fetched')

        out, dummy = nsca_send.communicate(nsca_message)
        if nsca_send.returncode != 0:
            raise RuntimeError('send_nsca failed. Output: %s' % out)
