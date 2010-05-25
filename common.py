import os
import re
import tempfile
import thread
import gtk

STATE_LOADING = 0
STATE_NULL = 1
STATE_PAUSED = 2
STATE_PLAYING = 3
STATE_BUFFERING = 4
DEFAULT_TEMPFILE_DIR = os.path.join('cream', 'youtube-player')


_cleanup_regexes = (
    (re.compile(r'(?P<amp>&)(?P<X>\w*[^;\w])'), lambda m: '&amp;'+m.group('X')),
    (re.compile(r'<br/?>'), ''),
    (re.compile(r'</?a.*?>'), '')
)
def cleanup_markup(s):
    for pattern, replace in _cleanup_regexes:
        s = pattern.sub(replace, s)
    return s


class Lock(object):
    def __init__(self, for_obj):
        self.obj_thread_ident = thread.get_ident()

    def __enter__(self):
        if thread.get_ident() != self.obj_thread_ident:
            gtk.gdk.threads_enter()

    def __exit__(self, *exc_stuff_that_nobody_needs):
        if thread.get_ident() != self.obj_thread_ident:
            gtk.gdk.threads_leave()


class NamedTempfile(object):
    """
    Reusable, named temporary file.

    A new temporary file is created only if no file named ``name`` in ``dir``
    exists, otherwise the existing file is reused.

    Can be used i.e. for caching thumbnails, stream data and so on.
    """
    def __init__(self, name, dir=DEFAULT_TEMPFILE_DIR, auto_delete=False, auto_open=True):
        self.dir = os.path.join(tempfile.gettempdir(), dir)
        self.name = os.path.join(self.dir, name)
        self.auto_delete = auto_delete

        self._ensure_dir_exists()
        self.file = self._open_file(self.name)
        if not auto_open:
            self.file.close()
            del self.file

    def isempty(self):
        return os.path.getsize(self.file.name) == 0

    def delete(self):
        self.file.close() # make sure the file is closed.
        os.remove(self.name)

    def _ensure_dir_exists(self):
        if not os.path.exists(self.dir):
            os.makedirs(self.dir)

    def _open_file(self, fname):
        if not os.path.exists(fname):
            return open(fname, 'w+')
        else:
            return open(fname, 'r+')

    def __del__(self):
        if self.auto_delete:
            self.delete()

    # context manager support
    def __enter__(self, *args, **kwargs):
        return self.file.__enter__(*args, **kwargs)

    def __exit__(self, *args, **kwargs):
        return self.file.__exit__(*args, **kwargs)
