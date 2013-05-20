import contextlib
import os
import shutil
import subprocess

import abstract
from utils import ssh

class OpenwrtLuciBackend(abstract.AbstractBackend):
    def __init__(self, hostname, settings):
        super(OpenwrtLuciBackend, self).__init__(hostname, settings)
        self.host = hostname
        self.settings = settings
        self.password = settings.pop('password', None)

    def get_config(self):
        self.session = ssh.SSHSession(
                ssh.gen_args(self.host, self.settings),
                password=self.password
        )

        with contextlib.closing(self.session):
            # Luci maintains a list of paths which should be backed up in flash_keep.
            # We first read those paths
            flash_keep = self.session.call("uci show luci.flash_keep")[:-1]
            paths = []

            for line in flash_keep.split('\n'):
                index = line.find('=')
                if index < 0:
                    raise RuntimeError('Couldn\'t parse uci output')
                path = line[index+1:]

                # Paths are given as absolute paths. Ignore everything else
                if path[0] != '/':
                    continue

                # Check if path actually exists
                check_cmd = 'if test -e "%s"; then echo "yes"; else echo "no"; fi' % path
                check_result = self.session.call(check_cmd).strip()
                if check_result != 'yes':
                    continue

                paths.append(path[1:])

            # Ensure this list is actually useful. If luci is not installed it might be
            # that we just generated an empty list. Backup shouldn't fail silently in that
            # case.
            if 'etc/config/' not in paths:
                raise RuntimeError('Sanity check failed. flash_keep did not contain /etc/config/')

            # Tar everything up. The output tarball should be usable with the 'restore backup'
            # option in the web interface. We encode it in hex to avoid transport issues
            tar_cmd = 'cd / && tar -cz ' + ' '.join(paths)
            tar_hex = self.session.call(tar_cmd + " | hexdump -v -e '1/1 \"%02x\"'")

            if len(tar_hex) % 2:
                raise RuntimeError("Unexpected format for hexdump")

            tarball = bytes()
            while tar_hex:
                tarball += chr(int(tar_hex[:2],16))
                tar_hex = tar_hex[2:]
            return tarball

    def store_config(self, config, path):
        if os.path.exists(path):
            shutil.rmtree(path)

        os.mkdir(path)
        tar = subprocess.Popen(['tar', '-xz', '-C', path], stdin=subprocess.PIPE)
        tar.communicate(config)
        if tar.returncode != 0:
            raise RuntimeError("Couldn't store config.")
