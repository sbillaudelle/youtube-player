import thread

import gtk
import gst

import cream

from youtube import YouTubeAPI

gtk.gdk.threads_init()

YOUTUBE_DEVELOPER_KEY = 'AI39si5ABc6YvX1MST8Q7O-uxN7Ra1ly-KKryqH7pc0fb8MrMvvVzvqenE2afoyjQB276fWVx1T3qpDi7FFO6tkVs7JqqTmRRA'

STATE_NULL = 0
STATE_PAUSED = 1
STATE_PLAYING = 2

class YouTubePlayer(cream.Module):

    state = STATE_NULL

    def __init__(self):

        cream.Module.__init__(self)

        # Build GTK+ interface:
        self.interface = gtk.Builder()
        self.interface.add_from_file('interface.ui')

        self.window = self.interface.get_object('window')
        self.video_area = self.interface.get_object('video_area')
        self.search_entry = self.interface.get_object('search_entry')
        self.play_pause_button = self.interface.get_object('play_pause_button')
        self.play_pause_image = self.interface.get_object('play_pause_image')
        self.liststore = self.interface.get_object('liststore')
        self.treeview = self.interface.get_object('treeview')

        self.video_area.connect('expose-event', self.expose_cb)
        self.search_entry.connect('activate', self.search_cb)
        self.play_pause_button.connect('clicked', self.play_pause_cb)
        self.treeview.connect('row-activated', self.row_activated_cb)

        # Connect to YouTube:
        self.youtube = YouTubeAPI(YOUTUBE_DEVELOPER_KEY)

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

        self.window.show_all()


    def expose_cb(self, source, event):

        ctx = self.video_area.window.cairo_create()

        ctx.set_source_rgb(0, 0, 0)
        ctx.paint()


    def search_cb(self, source):

        search_string = self.search_entry.get_text()
        self.search(search_string)


    def row_activated_cb(self, source, iter, path):

        selection = self.treeview.get_selection()
        model, iter = selection.get_selected()
        id = model.get_value(iter, 0)
        self.load_video(id)

        self.play()


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


    def search(self, search_string):

        self.liststore.clear()
        thread.start_new_thread(self._search, (search_string,))


    def _search(self, search_string):

        res = self.youtube.search(search_string)

        gtk.gdk.threads_enter()
        for video in res:
            self.videos[video.video_id] = video
            self.liststore.append((
                video.video_id,
                video.title,
                gtk.gdk.pixbuf_new_from_file('/home/stein/logo.svg').scale_simple(24, 24, gtk.gdk.INTERP_HYPER)
                ))
        gtk.gdk.threads_leave()


    def play(self):

        self.player.set_state(gst.STATE_PLAYING)
        self.state = STATE_PLAYING

        self.play_pause_image.set_from_icon_name('media-playback-pause', gtk.ICON_SIZE_BUTTON)


    def pause(self):

        self.player.set_state(gst.STATE_PAUSED)
        self.state = STATE_PAUSED

        self.play_pause_image.set_from_icon_name('media-playback-start', gtk.ICON_SIZE_BUTTON)


    def load_video(self, id):

        self.player.set_state(gst.STATE_NULL)
        self.state = STATE_NULL

        self.play_pause_image.set_from_icon_name('media-playback-start', gtk.ICON_SIZE_BUTTON)

        video = self.videos[id]
        self.playbin.set_property('uri', video.video_url)


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
            gtk.gdk.threads_enter()

            self.video_area.show()

            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            imagesink.set_xwindow_id(self.video_area.window.xid)

            gtk.gdk.threads_leave()


if __name__ == '__main__':
    youtube_player = YouTubePlayer()
    youtube_player.main()
