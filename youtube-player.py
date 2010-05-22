#!/usr/bin/env python
import thread
import math
import gobject
import gtk
import gst

import youtube
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


# <extracted from cream.gui>
CURVE_SINE = lambda x: math.sin(math.pi / 2 * x)
FRAMERATE  = 30.0
class Timeline(gobject.GObject):
    __gtype_name__ = 'Timeline'
    __gsignals__ = {
        'update': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_FLOAT,)),
        'completed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
        }

    def __init__(self, duration, curve):

        gobject.GObject.__init__(self)

        self.duration = duration
        self.curve = curve

        self._states = []


    def run(self):

        n_frames = (self.duration / 1000.0) * FRAMERATE

        while len(self._states) <= n_frames:
            self._states.append(self.curve(len(self._states) * (1.0 / n_frames)))
        self._states.reverse()

        gobject.timeout_add(int(self.duration / FRAMERATE), self.update)


    def update(self):

        self.emit('update', self._states.pop())
        if len(self._states) == 0:
            self.emit('completed')
            return False
        return True
# </extract>


class Slider(gtk.Viewport):

    def __init__(self):

        self.active_widget = None
        self._size_cache = None

        gtk.Viewport.__init__(self)
        self.set_shadow_type(gtk.SHADOW_NONE)

        self.layout = gtk.HBox(True)

        self.content = gtk.EventBox()
        self.content.add(self.layout)

        self.container = gtk.Fixed()
        self.container.add(self.content)
        self.add(self.container)

        self.connect('size-allocate', self.size_allocate_cb)


    def slide_to(self, widget):

        self.active_widget = widget

        def update(source, status):
            pos = end_position - start_position
            adjustment.set_value(start_position + int(round(status * pos)))

        adjustment = self.get_hadjustment()
        start_position = adjustment.get_value()
        end_position = widget.get_allocation().x

        if start_position != end_position:
            t = cream.gui.Timeline(500, cream.gui.CURVE_SINE)
            t.connect('update', update)
            t.run()


    def size_allocate_cb(self, source, allocation):

        if self._size_cache != allocation and self.active_widget:
            adjustment = self.get_hadjustment()
            adjustment.set_value(self.active_widget.get_allocation().x)

        self._size_cache = allocation

        width = (len(self.layout.get_children()) or 1) * allocation.width
        self.content.set_size_request(width, allocation.height)


    def append(self, widget):

        self.layout.pack_start(widget, True, True, 0)




class YouTubePlayer(object):
    state = STATE_NULL
    fullscreen = False
    preferred_resolution = '1080p'
    _current_video_id = None

    def __init__(self):

        self._main_thread_id = thread.get_ident()
        self._slide_to_info_timeout = None

        self._main_thread_id = thread.get_ident()
        self._slide_to_info_timeout = None

        # Build GTK+ interface:
        self.interface = gtk.Builder()
        self.interface.add_from_file('interface.ui')

        for obj in ('window', 'fullscreen_window', 'video_area', 'control_area',
                    'fullscreen_video_area', 'search_entry', 'play_pause_button',
                    'play_pause_image', 'resolution_chooser', 'resolutions_store',
                    'position_display', 'progress', 'liststore', 'treeview',
                    'cellrenderer_info', 'cellrenderer_thumbnail', 'sort_by_menu',
                    'sort_by_relevance', 'sort_by_published',
                    'info_box', 'search_box', 'back_to_search_button', 'sidebar',
                    'info_label_title', 'info_label_description'):
            setattr(self, obj, self.interface.get_object(obj))

        self.throbber = Throbber()

        self.slider = Slider()
        self.slider.append(self.search_box)
        self.slider.append(self.info_box)
        self.slider.set_size_request(240, 300)

        self.sidebar.add(self.slider)

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
        self.back_to_search_button.connect('clicked', self.back_to_search_button_clicked_cb)
        self.info_label_description.connect('size-allocate', lambda source, allocation: source.set_size_request(allocation.width - 2, -1))

        self.search_entry.connect('changed', lambda *args: self.extend_slide_to_info_timeout())
        self.search_entry.connect('motion-notify-event', lambda *args: self.extend_slide_to_info_timeout())
        self.treeview.connect('motion-notify-event', lambda *args: self.extend_slide_to_info_timeout())

        # Prefill the resolution combo box:
        for index, resolution in enumerate(youtube.RESOLUTIONS.itervalues()):
            self.resolutions_store.append((resolution,))
            if resolution == self.preferred_resolution:
                self.resolution_chooser.set_active(index)

        # Connect to YouTube:
        self.youtube = youtube.API(YOUTUBE_DEVELOPER_KEY)

        # Initialize GStreamer stuff:
        self.player = gst.Pipeline("player")

        self.playbin = gst.element_factory_make("playbin2", "playbin")
        self.video_sink = gst.element_factory_make("xvimagesink", "vsink")
        self.playbin.set_property('suburi', 'file:///home/stein/Labs/Experiments/Subtitles/foo.srt')
        self.playbin.set_property('subtitle-font-desc', 'Sans 14')
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

        gobject.timeout_add(200, self.update_progressbar)


    def remove_slide_to_info_timeout(self):

        if self._slide_to_info_timeout:
            gobject.source_remove(self._slide_to_info_timeout)


    def extend_slide_to_info_timeout(self):

        if self._slide_to_info_timeout:
            self.remove_slide_to_info_timeout()
            self._slide_to_info_timeout = gobject.timeout_add(5000, lambda *args: self.slider.slide_to(self.info_box))


    def back_to_search_button_clicked_cb(self, source):

        self.remove_slide_to_info_timeout()

        self.slider.slide_to(self.search_box)
        self._slide_to_info_timeout = gobject.timeout_add(5000, lambda: self.slider.slide_to(self.info_box))


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

            thumbnail = gtk.gdk.pixbuf_new_from_file_at_size(PLAYER_LOGO, int(logo_width), int(logo_height))
            ctx.set_source_pixbuf(thumbnail, logo_x, logo_y)
            ctx.paint()


    def search_cb(self, source):

        search_string = self.search_entry.get_text()
        self.search(search_string)

        self.extend_slide_to_info_timeout()


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
        self.preferred_resolution = self.resolutions_store.get_value(
                resolution_combobox.get_active_iter(), 0)
        if self._current_video_id:
            # User changed the quality while playing a video -- replay currently
            # played video with the selected quality.
            # TODO: Remember the seek here and re-seek to that point.
            thread.start_new_thread(self.load_video, (self._current_video_id,))


    def search(self, search_string):

        sort_by = youtube.SORT_BY_RELEVANCE
        if self.sort_by_published.get_active():
            sort_by = youtube.SORT_BY_PUBLISHED

        self.liststore.clear()
        thread.start_new_thread(self._search, (search_string, sort_by))


    def _search(self, search_string, sort_by=youtube.SORT_BY_RELEVANCE):

        search_result = self.youtube.search(search_string, sort_by)

        for video in search_result:
            self.videos[video.video_id] = video

            info = "<b>{0}</b>\n{1}\n{2}".format(video.title, video.description, convert_ns(int(video.duration) * 1000000000))
            thumbnail = gtk.gdk.pixbuf_new_from_file(PLAYER_LOGO).scale_simple(ICON_SIZE, ICON_SIZE, gtk.gdk.INTERP_HYPER)

            with gtk.gdk.lock:
                video._tree_iter = self.liststore.append((video.video_id, info, thumbnail, True))

        for column, row in enumerate(self.liststore):
            video = self.videos[row[0]]
            self._request_video_info(video)
            video_thumbnail = gtk.gdk.pixbuf_new_from_file(video.thumbnail_path or PLAYER_LOGO)
            row[2] = video_thumbnail.scale_simple(ICON_SIZE, ICON_SIZE, gtk.gdk.INTERP_HYPER)


    def _request_video_info(self, video):
        try:
            video.request_video_info()
        except youtube.YouTubeError:
            self.liststore.set_value(video._tree_iter, 3, False)


    def update_progressbar(self):

        try:
            duration_ns = self.player.query_duration(gst.FORMAT_TIME, None)[0]
            position_ns = self.player.query_position(gst.FORMAT_TIME, None)[0]
        except gst.QueryError:
            # Query failed; currently no video playing
            return True

        with gtk.gdk.lock:
            self.update_position(duration_ns, position_ns)

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


    def threads_enter(self):

        if self._main_thread_id != thread.get_ident():
            gtk.gdk.threads_enter()


    def threads_leave(self):

        if self._main_thread_id != thread.get_ident():
            gtk.gdk.threads_leave()


    def set_state(self, state):

        if state in [STATE_NULL, STATE_PAUSED, STATE_PLAYING]:
            self.threads_enter()
            if self.control_area.get_child() != self.play_pause_button:
                self.control_area.remove(self.throbber)
                self.control_area.add(self.play_pause_button)
            self.play_pause_button.set_sensitive(True)
            self.threads_leave()

        if state == STATE_NULL:
            self.player.set_state(gst.STATE_NULL)
            self.state = STATE_NULL

            self.threads_enter()
            self.update_position(0, 0)
            self.draw()
            self.play_pause_image.set_from_icon_name('media-playback-start', gtk.ICON_SIZE_BUTTON)
            self.threads_leave()

        elif state == STATE_PAUSED:
            self.player.set_state(gst.STATE_PAUSED)
            self.state = STATE_PAUSED

            self.threads_enter()
            self.play_pause_image.set_from_icon_name('media-playback-start', gtk.ICON_SIZE_BUTTON)
            self.threads_leave()

        elif state == STATE_PLAYING:
            self.player.set_state(gst.STATE_PLAYING)
            self.state = STATE_PLAYING

            self.threads_enter()
            self.draw()
            self.play_pause_image.set_from_icon_name('media-playback-pause', gtk.ICON_SIZE_BUTTON)
            self.threads_leave()

        elif state == STATE_BUFFERING:
            self.player.set_state(gst.STATE_PAUSED)
            self.state = STATE_BUFFERING

            self.threads_enter()
            if self.control_area.get_child() != self.throbber:
                self.throbber.set_size_request(self.play_pause_button.get_allocation().width, self.play_pause_button.get_allocation().height)
                self.control_area.remove(self.play_pause_button)
                self.control_area.add(self.throbber)
                self.throbber.show()
            self.threads_leave()


    def load_video(self, id, play=True):

        self.slider.slide_to(self.info_box)

        self.set_state(STATE_NULL)

        video = self.videos[id]

        self.info_label_title.set_text(video.title)
        self.info_label_description.set_text(video.description)

        self._request_video_info(video)
        try:
            video_url = video.stream_urls[self.preferred_resolution]
        except KeyError:
            # fallback: use the highest possible resolution
            video_url = video.stream_urls[video.stream_urls.keys()[0]]
        self.playbin.set_property('uri', video_url)
        self._current_video_id = id

        if play:
            self.set_state(STATE_PLAYING)


    def on_message(self, bus, message):

        type = message.type

        if type == gst.MESSAGE_EOS:
            self.remove_slide_to_info_timeout()
            self.slider.slide_to(self.search_box)
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
            with gtk.gdk.lock:
                self.video_area.show()

                imagesink = message.src
                imagesink.set_property("force-aspect-ratio", True)
                imagesink.set_xwindow_id(self.video_area.window.xid)


    def main(self):
        self._mainloop = gobject.MainLoop()
        self._mainloop.run()

    def quit(self):
        self._mainloop.quit()


if __name__ == '__main__':
    youtube_player = YouTubePlayer()
    youtube_player.main()
