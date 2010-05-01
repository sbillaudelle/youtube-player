import gtk
import gst

from youtube import YouTube

gtk.gdk.threads_init()

STATE_NULL = 0
STATE_PAUSED = 1
STATE_PLAYING = 2

class YouTubePlayer:

    state = STATE_NULL

    def __init__(self):

        # Build GTK+ interface:
        self.interface = gtk.Builder()
        self.interface.add_from_file('interface.ui')

        self.window = self.interface.get_object('window')
        self.play_pause_button = self.interface.get_object('play_pause_button')
        self.play_pause_image = self.interface.get_object('play_pause_image')
        self.liststore = self.interface.get_object('liststore')
        self.treeview = self.interface.get_object('treeview')

        self.play_pause_button.connect('clicked', self.play_pause_cb)

        # Connect to YouTube:
        self.youtube = YouTube()

        # Initialize GStreamer stuff:
        self.player = gst.Pipeline("player")

        self.playbin = gst.element_factory_make("playbin", "playbin")
        self.player.add(self.playbin)

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)

        self.videos = {}

        # Populate the liststore:
        res = self.youtube.search('The Cat Empire')
        for video in res:
            self.videos[video.id] = video
            self.liststore.append((
                video.id,
                video.title,
                gtk.gdk.pixbuf_new_from_file('/home/stein/logo.svg').scale_simple(24, 24, gtk.gdk.INTERP_HYPER)
                ))

        self.window.show_all()


    def play_pause_cb(self, source):

        if self.state == STATE_NULL:
            selection = self.treeview.get_selection()
            model, iter = selection.get_selected()
            id = model.get_value(iter, 0)
            self.load_video(id)

            self.play()
        elif self.state == STATE_PAUSED:
            self.play()
        else:
            self.pause()


    def play(self):

        self.player.set_state(gst.STATE_PLAYING)
        self.state = STATE_PLAYING

        self.play_pause_image.set_from_icon_name('media-playback-pause', gtk.ICON_SIZE_BUTTON)


    def pause(self):

        self.player.set_state(gst.STATE_PAUSED)
        self.state = STATE_PAUSED

        self.play_pause_image.set_from_icon_name('media-playback-start', gtk.ICON_SIZE_BUTTON)


    def load_video(self, id):

        video = self.videos[id]
        self.playbin.set_property('uri', video.get_video_uri())


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

            foo = self.interface.get_object('video_area')
            foo.show()

            imagesink.set_xwindow_id(foo.window.xid)
            gtk.gdk.threads_leave()


if __name__ == '__main__':
    YouTubePlayer()
    gtk.main()
