import gtk
import gst

gtk.gdk.threads_init()


class Foo:

    def __init__(self):

        self.interface = gtk.Builder()
        self.interface.add_from_file('interface.ui')

        self.interface.get_object('window1').show_all()
        self.interface.get_object('button1').connect('clicked', lambda *args: self.player.set_state(gst.STATE_PLAYING))

        self.player = gst.parse_launch ("filesrc location=/home/stein/Downloads/FlashForward.S01E18.720p.HDTV.x264-CTU.mkv ! decodebin ! autovideosink")

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)


    def on_message(self, bus, message):

        t = message.type

        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
        elif t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.player.set_state(gst.STATE_NULL)


    def on_sync_message(self, bus, message):

        if message.structure is None:
            return

        message_name = message.structure.get_name()

        if message_name == "prepare-xwindow-id":
            # Assign the viewport

            gtk.gdk.threads_enter()
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)

            foo = self.interface.get_object('drawingarea1')
            foo.show()

            imagesink.set_xwindow_id(foo.window.xid)
            gtk.gdk.threads_leave()


if __name__ == '__main__':
    Foo()
    gtk.main()
