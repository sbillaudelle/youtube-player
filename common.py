import thread
import gtk

STATE_NULL = 0
STATE_PAUSED = 1
STATE_PLAYING = 2
STATE_BUFFERING = 3


class Lock(object):
    def __init__(self, for_obj):
        self.obj = for_obj

    def __enter__(self):
        if thread.get_ident() != self.obj._main_thread_id:
            gtk.gdk.threads_enter()

    def __exit__(self, *exc_stuff_that_nobody_needs):
        if thread.get_ident() != self.obj._main_thread_id:
            gtk.gdk.threads_leave()
