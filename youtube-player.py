#!/usr/bin/env python
import thread

import gobject
import gtk
import gst

import cream

from youtube import YouTubeAPI, RESOLUTIONS, RELEVANCE, PUBLISHED
from throbber import Throbber

gtk.gdk.threads_init()

YOUTUBE_DEVELOPER_KEY = 'AI39si5ABc6YvX1MST8Q7O-uxN7Ra1ly-KKryqH7pc0fb8MrMvvVzvqenE2afoyjQB276fWVx1T3qpDi7FFO6tkVs7JqqTmRRA'

PLAYER_LOGO = 'youtube-player.svg'
ICON_SIZE = 64

STATE_NULL = 0
STATE_PAUSED = 1
STATE_PLAYING = 2
STATE_BUFFERING = 3


def convert_ns(t):
    s, ns = divmod(t, 1000000000)
    m, s = divmod(s, 60)

    if m < 60:
        return "%02i:%02i" %(m,s)
    else:
        h,m = divmod(m, 60)
        return "%i:%02i:%02i" %(h,m,s)


class YouTubePlayer(cream.Module):

    state = STATE_NULL
    fullscreen = False
    _current_video_id = None

    def __init__(self):

        cream.Module.__init__(self)

        # Build GTK+ interface:
        self.interface = gtk.Builder()
        self.interface.add_from_file('interface.ui')

        for obj in ('window', 'fullscreen_window', 'video_area', 'control_area',
                    'fullscreen_video_area', 'search_entry', 'play_pause_button',
                    'play_pause_image', 'resolution_chooser', 'resolutions_store',
                    'position_display', 'progress', 'liststore', 'treeview',
                    'cellrenderer_info', 'cellrenderer_thumbnail', 'sort_by_menu',
                    'sort_by_relevance', 'sort_by_published'):
            setattr(self, obj, self.interface.get_object(obj))

        self.throbber = Throbber()

        self.fullscreen_window.fullscreen()
        self.video_area.set_app_paintable(True)
        self.fullscreen_video_area.set_app_paintable(True)
        self.play_pause_image.set_from_icon_name('media-playback-start', gtk.ICON_SIZE_BUTTON)
        self.video_area.connect('expose-event', self.expose_cb)
        self.fullscreen_video_area.connect('expose-event', self.expose_cb) 
        self.search_entry.connect('activate', self.search_cb)
        self.search_entry.connect('icon-release', lambda *args: self.sort_by_menu.popup(None, None, None, 1, 0))
        self.play_pause_button.connect('clicked', self.play_pause_cb)
        self.resolution_chooser.connect('changed', self.resolution_changed_cb)
        self.treeview.connect('row-activated', self.row_activated_cb)
        self.treeview.connect('size-allocate', self.treeview_size_allocate_cb)
        self.window.connect('destroy', lambda *args: self.quit())
        self.video_area.connect('button-press-event', self.video_area_click_cb)
        self.fullscreen_video_area.connect('button-press-event', self.video_area_click_cb)
        self.sort_by_menu.connect('selection-done', self.search_cb)

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

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)

        self.videos = {}

        self.window.show_all()

        gobject.timeout_add(1000, self.update_progressbar)

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

            thumbnail = gtk.gdk.pixbuf_new_from_file_at_size(PLAYER_LOGO, logo_width, logo_height)
            ctx.set_source_pixbuf(thumbnail, logo_x, logo_y)
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
            self.set_state(STATE_PLAYING)
        else:
            self.set_state(STATE_PAUSED)

    def resolution_changed_cb(self, resolution_combobox):
        self.config.preferred_resolution = self.resolutions_store.get_value(
                resolution_combobox.get_active_iter(), 0)
        if self._current_video_id:
            # User changed the quality while playing a video -- replay currently
            # played video with the selected quality.
            # TODO: Remember the seek here and re-seek to that point.
            thread.start_new_thread(self.load_video, (self._current_video_id,))


    def search(self, search_string):

        sort_by = RELEVANCE
        if self.sort_by_relevance.get_active():
            sort_by = RELEVANCE
        elif self.sort_by_published.get_active():
            sort_by = PUBLISHED

        self.liststore.clear()
        thread.start_new_thread(self._search, (search_string, sort_by))


    def _search(self, search_string, sort_by=RELEVANCE):

        search_result = self.youtube.search(search_string, sort_by)

        for video in search_result:
            self.videos[video.video_id] = video

            info = "<b>{0}</b>\n{1}\n{2}".format(video.title, video.description, convert_ns(int(video.duration) * 1000000000))
            thumbnail = gtk.gdk.pixbuf_new_from_file(PLAYER_LOGO).scale_simple(ICON_SIZE, ICON_SIZE, gtk.gdk.INTERP_HYPER)

            gtk.gdk.threads_enter()
            self.liststore.append((
                video.video_id,
                info,
                thumbnail
            ))
            gtk.gdk.threads_leave()

        for column, row in enumerate(self.liststore):
            video = self.videos[row[0]]
            video_thumbnail = gtk.gdk.pixbuf_new_from_file(video.thumbnail_path or PLAYER_LOGO)
            row[2] = video_thumbnail.scale_simple(ICON_SIZE, ICON_SIZE, gtk.gdk.INTERP_HYPER)


    def update_progressbar(self):

        try:
            duration_ns = self.player.query_duration(gst.FORMAT_TIME, None)[0]
            position_ns = self.player.query_position(gst.FORMAT_TIME, None)[0]
        except gst.QueryError:
            # Query failed; currently no video playing
            return True

        gtk.gdk.threads_enter()
        self.update_position(duration_ns, position_ns)
        gtk.gdk.threads_leave()

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


    def set_state(self, state):

        if state in [STATE_NULL, STATE_PAUSED, STATE_PLAYING]:
            gtk.gdk.threads_enter()
            if self.control_area.get_child() != self.play_pause_button:
                self.control_area.remove(self.throbber)
                self.control_area.add(self.play_pause_button)
            self.play_pause_button.set_sensitive(True)
            gtk.gdk.threads_leave()

        if state == STATE_NULL:
            self.player.set_state(gst.STATE_NULL)
            self.state = STATE_NULL

            gtk.gdk.threads_enter()
            self.update_position(0, 0)
            self.draw()
            self.play_pause_image.set_from_icon_name('media-playback-start', gtk.ICON_SIZE_BUTTON)
            gtk.gdk.threads_leave()

        elif state == STATE_PAUSED:
            self.player.set_state(gst.STATE_PAUSED)
            self.state = STATE_PAUSED

            gtk.gdk.threads_enter()
            self.play_pause_image.set_from_icon_name('media-playback-start', gtk.ICON_SIZE_BUTTON)
            gtk.gdk.threads_leave()

        elif state == STATE_PLAYING:
            self.player.set_state(gst.STATE_PLAYING)
            self.state = STATE_PLAYING

            gtk.gdk.threads_enter()
            self.draw()
            self.play_pause_image.set_from_icon_name('media-playback-pause', gtk.ICON_SIZE_BUTTON)
            gtk.gdk.threads_leave()

        elif state == STATE_BUFFERING:
            self.player.set_state(gst.STATE_PAUSED)
            self.state = STATE_BUFFERING

            gtk.gdk.threads_enter()
            if self.control_area.get_child() != self.throbber:
                self.throbber.set_size_request(self.play_pause_button.get_allocation().width, self.play_pause_button.get_allocation().height)
                self.control_area.remove(self.play_pause_button)
                self.control_area.add(self.throbber)
                self.throbber.show()
            gtk.gdk.threads_leave()


    def load_video(self, id, play=True):

        self.set_state(STATE_NULL)

        video = self.videos[id]
        video_url = video.get_video_url(
            resolution=self.config.preferred_resolution,
            fallback_to_lower_resolution=True
        )
        self.playbin.set_property('uri', video_url)
        self._current_video_id = id

        if play:
            self.set_state(STATE_PLAYING)


    def on_message(self, bus, message):

        type = message.type

        if type == gst.MESSAGE_EOS:
            self.set_state(STATE_NULL)
        elif type == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            self.player.set_state(gst.STATE_NULL)
        elif type == gst.MESSAGE_BUFFERING:
            state = message.parse_buffering()
            self.throbber.set_progress(state / 100.0)
            if state < 100:
                if self.state == STATE_PLAYING:
                    self.set_state(STATE_BUFFERING)
            else:
                if self.state == STATE_BUFFERING:
                    self.set_state(STATE_PLAYING)


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
