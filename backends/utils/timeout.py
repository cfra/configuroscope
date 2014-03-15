import contextlib
import signal

class TimeoutError(Exception):
    pass

def handle_timeout(signum, frame):
    raise TimeoutError()

@contextlib.contextmanager
def timeout(msec):
    orig_handler = signal.signal(signal.SIGALRM, handle_timeout)
    signal.alarm(msec/1000)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, orig_handler)
