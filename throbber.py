import math

import gtk
import cairo

class Throbber(gtk.Widget):

    __gtype_name__ = 'Throbber'

    def __init__(self):

        gtk.Widget.__init__(self)

        self.progress = 0


    def do_realize(self):

        self.set_flags(self.flags() | gtk.REALIZED | gtk.NO_WINDOW)
        self.window = self.get_parent_window()
        self.style.attach(self.window)


    def do_size_request(self, requisition):

        width, height = 32, 32
        requisition.width = width
        requisition.height = height


    def do_size_allocate(self, allocation):
        self.allocation = allocation


    def do_expose_event(self, event):
        self._draw()


    def set_progress(self, progress):

        self.progress = progress
        if self.flags() & gtk.REALIZED:
            self.draw()


    def draw(self):

        self.window.invalidate_rect(self.allocation, True)


    def _draw(self):

        style = self.get_style()
        background = style.dark[gtk.STATE_NORMAL]
        border = style.dark[gtk.STATE_NORMAL]

        width = self.allocation.width
        height = self.allocation.height

        factor = min(width, height)

        ctx = self.window.cairo_create()
        ctx.set_operator(cairo.OPERATOR_OVER)

        ctx.translate(self.allocation.x, self.allocation.y)
        ctx.set_line_width(1)

        ctx.set_source_rgba(background.red / 65535.0, background.green / 65535.0, background.blue / 65535.0, .5)
        ctx.arc(.5 * width, .5 * height, .45 * factor, -.5 * math.pi, (-.5 + 2 * self.progress) * math.pi)
        ctx.line_to(.5 * width, .5 * height)
        ctx.close_path()
        ctx.fill_preserve()
        ctx.set_source_rgba(border.red / 65535.0, border.green / 65535.0, border.blue / 65535.0, 1)
        ctx.stroke()


if __name__ == '__main__':
    win = gtk.Window()
    win.add(Throbber())
    win.show_all()
    gtk.main()
