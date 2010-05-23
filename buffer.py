import tempfile

import gobject
import gst

from common import STATE_BUFFERING, STATE_NULL, STATE_PAUSED, STATE_PLAYING

class BufferException(BaseException):
    pass


class Buffer(gobject.GObject):
    # TODO: One buffer for each video -- one buffer file for each video

    __gtype_name__ = 'Buffer'
    __gsignals__ = {
        'ready': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
        'update': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT,))
        }

    def __init__(self):

        gobject.GObject.__init__(self)

        self.state = STATE_NULL
        self.ready = False
        self.eos = False
        self.update_timeout = None

        self.pipeline = gst.parse_launch('souphttpsrc name=src ! filesink name=sink sync=false')
        self.src = self.pipeline.get_by_name('src')
        self.sink = self.pipeline.get_by_name('sink')

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self.bus_message_cb)


        self.test_pipeline = gst.parse_launch('filesrc name=test_src ! decodebin2 ! fakesink')
        self.test_src = self.test_pipeline.get_by_name('test_src')

        self.test_bus = self.test_pipeline.get_bus()
        self.test_bus.add_signal_watch()
        self.test_bus.connect("message", self.test_bus_message_cb)


    def bus_message_cb(self, bus, message):

        t = message.type

        if t == gst.MESSAGE_EOS:
            self.eos = True


    def test_bus_message_cb(self, bus, message):

        t = message.type

        if t == gst.MESSAGE_TAG:
            self.emit('ready')
            self.ready = True
            self.test_pipeline.set_state(gst.STATE_NULL)
        elif t == gst.MESSAGE_ERROR:
            self.test_pipeline.set_state(gst.STATE_NULL)


    def update(self):

        if self.eos:
            self.emit('update', 100)
            return
        try:
            duration = self.pipeline.query_duration(gst.FORMAT_BYTES, None)[0]
            position = self.pipeline.query_position(gst.FORMAT_BYTES, None)[0]
            self.emit('update', float(position) / float(duration) * 100)
            if not self.ready:
                self.test_pipeline.set_state(gst.STATE_PLAYING)
        except gst.QueryError:
            duration = 0
            position = 0

        return True


    def load(self, uri):

        self.ready = False

        self.src.set_property('location', uri)

        tmp = tempfile.mktemp(dir='/tmp')
        self.sink.set_property('location', tmp)
        self.test_src.set_property('location', tmp)

        return tmp


    def flush(self):

        self.ready = False
        self.eos = False

        self.set_state(STATE_NULL)

        self.emit('update', 0)


    def set_state(self, state):

        if state not in [STATE_NULL, STATE_PLAYING]:
            raise BufferException, "'state' must be either 'STATE_NULL' or 'STATE_PLAYING', not '{0}'!".format(state)

        if state == STATE_NULL:
            self.pipeline.set_state(gst.STATE_NULL)
            if self.update_timeout:
                gobject.source_remove(self.update_timeout)
                self.update_timeout = None
            self.state = STATE_NULL
        elif state == STATE_PLAYING:
            self.pipeline.set_state(gst.STATE_PLAYING)
            if self.update_timeout:
                gobject.source_remove(self.update_timeout)
            self.update_timeout = gobject.timeout_add(100, self.update)
            self.state = STATE_PLAYING
