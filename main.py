import traceback

from kivy.app import App
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView


def error_view(text):
    sv = ScrollView()
    with sv.canvas.before:
        Color(0, 0, 0, 1)
        bg = Rectangle(pos=sv.pos, size=sv.size)
    sv.bind(pos=lambda i, v: setattr(bg, 'pos', v),
            size=lambda i, v: setattr(bg, 'size', v))
    lbl = Label(text=text, size_hint_y=None, halign='left',
                valign='top', font_size='13sp')
    lbl.bind(width=lambda i, w: setattr(i, 'text_size', (w, None)))
    lbl.bind(texture_size=lambda i, s: setattr(i, 'height', s[1]))
    sv.add_widget(lbl)
    return sv


class ShowErrors(ExceptionHandler):
    shown = False

    def handle_exception(self, inst):
        if not ShowErrors.shown:
            ShowErrors.shown = True
            Window.add_widget(error_view(traceback.format_exc()))
        return ExceptionManager.PASS


class ErrorApp(App):
    def __init__(self, error_text, **kw):
        super().__init__(**kw)
        self.error_text = error_text

    def build(self):
        return error_view(self.error_text)


ExceptionManager.add_handler(ShowErrors())

try:
    import game_ui
    game_ui.TowerDefenseApp().run()
except Exception:
    ErrorApp(traceback.format_exc()).run()
