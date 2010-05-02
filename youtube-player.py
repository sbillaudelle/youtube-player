#!/usr/bin/env python
import thread

import gobject
import gtk
import gst

import cream

from youtube import YouTubeAPI, RESOLUTIONS

gtk.gdk.threads_init()

YOUTUBE_DEVELOPER_KEY = 'AI39si5ABc6YvX1MST8Q7O-uxN7Ra1ly-KKryqH7pc0fb8MrMvvVzvqenE2afoyjQB276fWVx1T3qpDi7FFO6tkVs7JqqTmRRA'

ICON_SIZE = 64

STATE_NULL = 0
STATE_PAUSED = 1
STATE_PLAYING = 2

def convert_ns(t):
    s,ns = divmod(t, 1000000000)
    m,s = divmod(s, 60)

    if m < 60:
        return "%02i:%02i" %(m,s)
    else:
        h,m = divmod(m, 60)
        return "%i:%02i:%02i" %(h,m,s)


class YouTubePlayer(cream.Module):

    state = STATE_NULL
    _current_video_id = None
    fullscreen = False

    def __init__(self):

        cream.Module.__init__(self)

        # Build GTK+ interface:
        self.interface = gtk.Builder()
        self.interface.add_from_file('interface.ui')

        self.window = self.interface.get_object('window')
        self.fullscreen_window = self.interface.get_object('fullscreen_window')
        self.video_area = self.interface.get_object('video_area')
        self.fullscreen_video_area = self.interface.get_object('fullscreen_video_area')
        self.search_entry = self.interface.get_object('search_entry')
        self.play_pause_button = self.interface.get_object('play_pause_button')
        self.play_pause_image = self.interface.get_object('play_pause_image')
        self.resolution_chooser = self.interface.get_object('resolution_chooser')
        self.resolutions_store = self.interface.get_object('resolutions_store')
        self.position_display = self.interface.get_object('position_display')
        self.progress = self.interface.get_object('progress')
        self.liststore = self.interface.get_object('liststore')
        self.treeview = self.interface.get_object('treeview')
        self.cellrenderer_info = self.interface.get_object('cellrenderer_info')
        self.cellrenderer_thumbnail = self.interface.get_object('cellrenderer_thumbnail')

        self.fullscreen_window.fullscreen()
        self.video_area.set_app_paintable(True)
        self.fullscreen_video_area.set_app_paintable(True)

        self.video_area.connect('expose-event', self.expose_cb)
        self.fullscreen_video_area.connect('expose-event', self.expose_cb)
        self.search_entry.connect('activate', self.search_cb)
        self.play_pause_button.connect('clicked', self.play_pause_cb)
        self.resolution_chooser.connect('changed', self.resolution_changed_cb)
        self.treeview.connect('row-activated', self.row_activated_cb)
        self.treeview.connect('size-allocate', self.treeview_size_allocate_cb)
        self.window.connect('destroy', lambda *args: self.quit())
        self.video_area.connect('button-press-event', self.video_area_click_cb)
        self.fullscreen_video_area.connect('button-press-event', self.video_area_click_cb)

        # Prefill the resolution combo box:
        for index, resolution in enumerate(RESOLUTIONS.iterkeys()):
            self.resolutions_store.append((resolution,))
            if resolution == self.config.preferred_resolution:
                self.resolution_chooser.set_active(index)


        # Connect to YouTube:
        self.youtube = YouTubeAPI(YOUTUBE_DEVELOPER_KEY)

        # Initialize GStreamer stuff:
        self.player = gst.Pipeline("player")

        self.playbin = gst.element_factory_make("playbin2", "playbin")
        self.video_sink = gst.element_factory_make("xvimagesink", "vsink")
        self.playbin.set_property('video-sink', self.video_sink)
        self.playbin.set_property('buffer-duration', 3000000000)
        self.playbin.set_property('buffer-size', 2000000000)
        self.player.add(self.playbin)

        self.playbin.set_property('flags', 255)

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)

        self.videos = {}

        self.window.show_all()

        gobject.timeout_add(1000, self.update)


    def treeview_size_allocate_cb(self, source, allocation):
        self.cellrenderer_info.set_property('width', allocation.width - ICON_SIZE - 8)


    def video_area_click_cb(self, source, event):

        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.toggle_fullscreen()


    def toggle_fullscreen(self):

        if not self.fullscreen:
            self.fullscreen_window.show_all()
            if self.fullscreen_window.window:
                self.video_sink.set_xwindow_id(self.fullscreen_video_area.window.xid)
            else:
                self.fullscreen_window.connect('map', lambda *args: self.video_sink.set_xwindow_id(self.fullscreen_video_area.window.xid))
            self.fullscreen = True
        else:
            self.fullscreen_window.hide()
            self.video_sink.set_xwindow_id(self.video_area.window.xid)
            self.fullscreen = False


    def expose_cb(self, source, event):
        self.draw()


    def draw(self):

        if self.fullscreen:
            video_area = self.fullscreen_video_area
        else:
            video_area = self.video_area

        width = video_area.get_allocation().width
        height = video_area.get_allocation().height

        if self.fullscreen:
            ctx = video_area.window.cairo_create()
        else:
            ctx = video_area.window.cairo_create()

        ctx.set_source_rgb(0, 0, 0)
        ctx.paint()

        if self.state == STATE_NULL:
            logo_width = logo_height = min(.4 * width, .4 * height)
    
            logo_x = (width - logo_width) / 2.0
            logo_y = (height - logo_height) / 2.0
    
            pb = gtk.gdk.pixbuf_new_from_file_at_size('youtube-player.svg', logo_width, logo_height)
            ctx.set_source_pixbuf(pb, logo_x, logo_y)
            ctx.paint()


    def search_cb(self, source):

        search_string = self.search_entry.get_text()
        self.search(search_string)


    def row_activated_cb(self, source, iter, path):

        selection = self.treeview.get_selection()
        model, iter = selection.get_selected()
        id = model.get_value(iter, 0)
        thread.start_new_thread(self.load_video, (id,))


    def play_pause_cb(self, source):

        if self.state == STATE_NULL:
            selection = self.treeview.get_selection()
            model, iter = selection.get_selected()
            id = model.get_value(iter, 0)
            thread.start_new_thread(self.load_video, (id,))
        elif self.state == STATE_PAUSED:
            self.play()
        else:
            self.pause()

    def resolution_changed_cb(self, resolution_combobox):
        self.config.preferred_resolution = self.resolutions_store.get_value(
                resolution_combobox.get_active_iter(), 0)
        if self._current_video_id:
            # User changed the quality while playing a video -- replay currently
            # played video with the selected quality.
            # TODO: Remember the seek here and re-seek to that point.
            thread.start_new_thread(self.load_video, (self._current_video_id,))


    def search(self, search_string):

        self.liststore.clear()
        thread.start_new_thread(self._search, (search_string,))


    def _search(self, search_string):

        res = self.youtube.search(search_string)

        for video in res:
            self.videos[video.video_id] = video

            info = "<b>{0}</b>\n{1}\n{2}".format(video.title, video.description, convert_ns(int(video.duration) * 1000000000))
            pb = gtk.gdk.pixbuf_new_from_file('youtube-player.svg').scale_simple(ICON_SIZE, ICON_SIZE, gtk.gdk.INTERP_HYPER)

            gtk.gdk.threads_enter()
            self.liststore.append((
                video.video_id,
                info,
                pb
                ))
            gtk.gdk.threads_leave()

        for c, row in enumerate(self.liststore):
            video = self.videos[row[0]]
            pb = gtk.gdk.pixbuf_new_from_file(video.thumbnail_path or 'youtube-player.svg').scale_simple(ICON_SIZE, ICON_SIZE, gtk.gdk.INTERP_HYPER)
            row[2] = pb


    def update(self):

        try:
            duration_ns = self.player.query_duration(gst.FORMAT_TIME, None)[0]
            position_ns = self.player.query_position(gst.FORMAT_TIME, None)[0]

            gtk.gdk.threads_enter()
            self.update_position(duration_ns, position_ns)
            gtk.gdk.threads_leave()
        except:
            pass

        return True


    def update_position(self, duration_ns, position_ns):

        duration = convert_ns(duration_ns)
        position = convert_ns(position_ns)

        if duration_ns != 0:
            percentage = (float(position_ns) / float(duration_ns)) * 100.0
        else:
            percentage = 0

        self.position_display.set_text("{0}/{1}".format(position, duration))
        self.progress.set_value(percentage)


    def play(self):

        self.player.set_state(gst.STATE_PLAYING)
        self.state = STATE_PLAYING

        self.draw()

        self.play_pause_image.set_from_icon_name('media-playback-pause', gtk.ICON_SIZE_BUTTON)


    def pause(self):

        self.player.set_state(gst.STATE_PAUSED)
        self.state = STATE_PAUSED

        self.play_pause_image.set_from_icon_name('media-playback-start', gtk.ICON_SIZE_BUTTON)


    def load_video(self, id, play=True):

        self.player.set_state(gst.STATE_NULL)
        self.state = STATE_NULL

        gtk.gdk.threads_enter()
        self.update_position(0, 0)
        gtk.gdk.threads_leave()

        self.draw()

        gtk.gdk.threads_enter()
        self.play_pause_image.set_from_icon_name('media-playback-start', gtk.ICON_SIZE_BUTTON)
        gtk.gdk.threads_leave()

        video = self.videos[id]
        video_url = video.get_video_url(
            resolution=self.config.preferred_resolution,
            fallback_to_lower_resolution=True
        )
        self.playbin.set_property('uri', video_url)
        self._current_video_id = id

        if play:
            self.play()


    def on_message(self, bus, message):

        t = message.type

        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
            self.update_position(0, 0)
        elif t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.player.set_state(gst.STATE_NULL)
        elif t == gst.MESSAGE_BUFFERING:
            state = message.parse_buffering()
            print "Buffering... ({0}%)".format(state)
            if state < 100:
                self.pause()
            else:
                self.play()


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
