import os
import tempfile
import thread
import gtk

STATE_NULL = 0
STATE_PAUSED = 1
STATE_PLAYING = 2
STATE_BUFFERING = 3
DEFAULT_TEMPFILE_DIR = os.path.join('cream', 'youtube-player')


class Lock(object):
    def __init__(self, for_obj):
        self.obj = for_obj

    def __enter__(self):
        if thread.get_ident() != self.obj._main_thread_id:
            gtk.gdk.threads_enter()

    def __exit__(self, *exc_stuff_that_nobody_needs):
        if thread.get_ident() != self.obj._main_thread_id:
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
            # make sure the file is closed.
            self.file.close()
            os.remove(self.name)

    # context manager support
    def __enter__(self):
        return self.file

    def __exit__(self, *args):
        return self.file.__exit__(*args)
