"""Tower Defense на Python + Kivy (собирается в APK через Buildozer)."""
import math

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.utils import platform

from engine import COLS, ROWS, PATH, TOWERS, MODES, Game
from sfx import SFX

if platform not in ('android', 'ios'):
    Window.size = (1100, 560)  # для запуска на компьютере
Window.clearcolor = (0.05, 0.06, 0.08, 1)


class Field(Widget):
    """Игровое поле: рисует состояние Game и превращает касания в клетки."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.game = Game()
        self.speed = 1
        self.paused = True  # пока не выбран режим
        self.hud = None
        self.cell, self.ox, self.oy = 40.0, 0.0, 0.0
        self.bind(pos=self.update_geometry, size=self.update_geometry)
        self.update_geometry()
        Clock.schedule_interval(self.tick, 1 / 60.0)

    # ----- геометрия и фон -----
    def update_geometry(self, *_):
        self.cell = max(1.0, min(self.width / COLS, self.height / ROWS))
        self.ox = self.x + (self.width - self.cell * COLS) / 2
        self.oy = self.y + (self.height - self.cell * ROWS) / 2
        self.draw_background()

    def draw_background(self):
        s = self.cell
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.07, 0.09, 0.07)
            Rectangle(pos=self.pos, size=self.size)
            for c in range(COLS):
                for r in range(ROWS):
                    if (c, r) in PATH:
                        Color(0.55, 0.43, 0.27)
                    elif (c + r) % 2:
                        Color(0.17, 0.30, 0.17)
                    else:
                        Color(0.15, 0.27, 0.15)
                    Rectangle(pos=(self.ox + c * s, self.oy + r * s), size=(s, s))

    # ----- игровой цикл -----
    def tick(self, dt):
        dt = min(dt, 0.05)
        g = self.game
        if not self.paused:
            for _ in range(self.speed):
                g.update(dt)
        for name in g.events:
            SFX.play(name)
        del g.events[:]
        self.redraw()
        if self.hud:
            self.hud()

    def redraw(self):
        g, s = self.game, self.cell
        ox, oy = self.ox, self.oy
        self.canvas.clear()
        with self.canvas:
            t = g.selected
            if t:
                Color(1, 1, 1, 0.13)
                Ellipse(pos=(ox + (t.x - t.range) * s, oy + (t.y - t.range) * s),
                        size=(2 * t.range * s, 2 * t.range * s))
                Color(1, 1, 1, 0.7)
                Line(circle=(ox + t.x * s, oy + t.y * s, t.range * s), width=dp(1.2))

            for t in g.towers:
                cx, cy = ox + t.x * s, oy + t.y * s
                Color(0.22, 0.22, 0.28)
                Ellipse(pos=(cx - 0.4 * s, cy - 0.4 * s), size=(0.8 * s, 0.8 * s))
                Color(*TOWERS[t.kind]['color'])
                Ellipse(pos=(cx - 0.28 * s, cy - 0.28 * s), size=(0.56 * s, 0.56 * s))
                Color(1, 1, 1)
                Line(points=[cx, cy, cx + math.cos(t.angle) * 0.45 * s,
                             cy + math.sin(t.angle) * 0.45 * s], width=dp(2))
                Color(1, 0.95, 0.4)
                for i in range(t.level):
                    Ellipse(pos=(cx - 0.3 * s + i * 0.2 * s, cy - 0.46 * s),
                            size=(0.12 * s, 0.12 * s))
                if t is g.selected:
                    Color(1, 0.9, 0.2)
                    Line(rectangle=(cx - 0.45 * s, cy - 0.45 * s, 0.9 * s, 0.9 * s),
                         width=dp(1.5))

            # сначала наземные враги, потом летуны (они рисуются поверх)
            for e in sorted(g.enemies, key=lambda en: en.fly):
                ex, ey, r = ox + e.x * s, oy + e.y * s, e.r * s
                Color(*((0.45, 0.75, 1.0) if e.slow_t > 0 else e.color))
                Ellipse(pos=(ex - r, ey - r), size=(2 * r, 2 * r))
                if e.armor:  # броня: светлая обводка
                    Color(0.95, 0.95, 1.0)
                    Line(circle=(ex, ey, r), width=dp(2))
                if e.fly:  # летун: кольцо вокруг
                    Color(1, 1, 1, 0.8)
                    Line(circle=(ex, ey, r + 0.1 * s), width=dp(1.3))
                if e.kind == 'healer':  # целитель: белый крест
                    Color(1, 1, 1)
                    Line(points=[ex - r * 0.55, ey, ex + r * 0.55, ey], width=dp(2))
                    Line(points=[ex, ey - r * 0.55, ex, ey + r * 0.55], width=dp(2))
                if e.kind == 'splitter':  # делитель: тёмная точка в центре
                    Color(0.15, 0.3, 0.05)
                    Ellipse(pos=(ex - r * 0.35, ey - r * 0.35), size=(r * 0.7, r * 0.7))
                w, h = 0.7 * s, 0.08 * s
                Color(0.25, 0.0, 0.0)
                Rectangle(pos=(ex - w / 2, ey + r + 0.04 * s), size=(w, h))
                Color(0.25, 0.9, 0.25)
                Rectangle(pos=(ex - w / 2, ey + r + 0.04 * s),
                          size=(w * max(0.0, e.hp / e.max_hp), h))

            for b in g.bullets:
                Color(*b.color)
                r = 0.09 * s
                Ellipse(pos=(ox + b.x * s - r, oy + b.y * s - r), size=(2 * r, 2 * r))

            for x, y, rad, life, col in g.flashes:
                Color(col[0], col[1], col[2], min(1.0, life * 2))
                Ellipse(pos=(ox + (x - rad) * s, oy + (y - rad) * s),
                        size=(2 * rad * s, 2 * rad * s))

            if g.game_over:
                Color(0, 0, 0, 0.6)
                Rectangle(pos=self.pos, size=self.size)

    # ----- ввод -----
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if self.game.game_over:
            self.game.reset()  # тот же режим
            return True
        col = int(math.floor((touch.x - self.ox) / self.cell))
        row = int(math.floor((touch.y - self.oy) / self.cell))
        self.game.tap(col, row)
        return True


class Overlay(BoxLayout):
    """Полноэкранная панель, которая не пропускает касания к полю под ней."""

    def __init__(self, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(0.04, 0.05, 0.07, 0.97)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.sync_bg, size=self.sync_bg)

    def sync_bg(self, *_):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def on_touch_down(self, touch):
        super().on_touch_down(touch)
        return True


class ModeButton(Button):
    """Кнопка выбора режима: название и описание."""

    def __init__(self, key, mode, **kw):
        super().__init__(markup=True, halign='center', valign='middle',
                         font_size=sp(16), **kw)
        self.mode_key = key
        self.text = f"[b]{mode['name']}[/b]\n[size=12sp]{mode['desc']}[/size]"
        self.bind(size=self.wrap_text)

    def wrap_text(self, inst, size):
        inst.text_size = (size[0] - dp(16), size[1] - dp(8))


class Root(FloatLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        column = BoxLayout(orientation='vertical')

        # верхняя панель: информация, звук, меню
        top_bar = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(3),
                            padding=dp(2))
        self.info_label = Label(font_size=sp(14), halign='left', valign='middle',
                                shorten=True)
        self.info_label.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        self.b_sound = Button(text='Звук: вкл', size_hint_x=None, width=dp(96),
                              font_size=sp(12))
        self.b_sound.bind(on_release=self.toggle_sound)
        self.b_menu = Button(text='Меню', size_hint_x=None, width=dp(80),
                             font_size=sp(12))
        self.b_menu.bind(on_release=self.show_menu)
        for w in (self.info_label, self.b_sound, self.b_menu):
            top_bar.add_widget(w)

        self.field = Field()
        self.field.hud = self.refresh

        # нижняя панель: башни и управление
        bar = BoxLayout(size_hint_y=None, height=dp(62), spacing=dp(3), padding=dp(3))
        self.tower_buttons = {}
        for kind, d in TOWERS.items():
            b = ToggleButton(text=f"{d['name']}\n{d['cost']}", group='towers',
                             halign='center', font_size=sp(13))
            b.bind(state=lambda inst, st, k=kind: self.pick(k, st))
            self.tower_buttons[kind] = b
            bar.add_widget(b)

        self.b_up = Button(text='Улучшить', halign='center', font_size=sp(13))
        self.b_up.bind(on_release=lambda *_: self.field.game.upgrade_selected())
        self.b_sell = Button(text='Продать', halign='center', font_size=sp(13))
        self.b_sell.bind(on_release=lambda *_: self.field.game.sell_selected())
        self.b_speed = Button(text='x1', font_size=sp(15))
        self.b_speed.bind(on_release=self.toggle_speed)
        self.b_wave = Button(text='Старт', halign='center', font_size=sp(13))
        self.b_wave.bind(on_release=lambda *_: self.field.game.start_wave())
        for b in (self.b_up, self.b_sell, self.b_speed, self.b_wave):
            bar.add_widget(b)

        column.add_widget(top_bar)
        column.add_widget(self.field)
        column.add_widget(bar)
        self.add_widget(column)

        self.msg = Label(font_size=sp(26), halign='center', valign='middle')
        self.msg.bind(size=lambda inst, v: setattr(inst, 'text_size', v))
        self.add_widget(self.msg)

        # меню выбора режима (поверх всего)
        self.menu = Overlay(orientation='vertical', padding=dp(14), spacing=dp(10))
        title = Label(text='[b]TOWER DEFENSE[/b]', markup=True, font_size=sp(30),
                      size_hint_y=None, height=dp(52))
        subtitle = Label(text='Выбери режим', font_size=sp(15),
                         size_hint_y=None, height=dp(24))
        grid = GridLayout(cols=3, spacing=dp(8))
        for key, mode in MODES.items():
            mb = ModeButton(key, mode)
            mb.bind(on_release=lambda inst: self.start_mode(inst.mode_key))
            grid.add_widget(mb)
        for w in (title, subtitle, grid):
            self.menu.add_widget(w)
        self.add_widget(self.menu)

        Window.bind(on_keyboard=self.on_key)

    # ----- меню и управление -----
    def start_mode(self, key):
        self.field.game.reset(key)
        self.field.speed = 1
        self.b_speed.text = 'x1'
        self.field.paused = False
        if self.menu.parent is not None:
            self.remove_widget(self.menu)

    def show_menu(self, *_):
        self.field.paused = True
        if self.menu.parent is None:
            self.add_widget(self.menu)

    def on_key(self, window, key, *args):
        # кнопка «Назад» на Android: из игры — в меню
        if key == 27 and self.menu.parent is None:
            self.show_menu()
            return True
        return False

    def toggle_sound(self, *_):
        SFX.enabled = not SFX.enabled
        self.b_sound.text = 'Звук: вкл' if SFX.enabled else 'Звук: выкл'

    def pick(self, kind, state):
        g = self.field.game
        if state == 'down':
            g.build_kind = kind
            g.selected = None
        elif g.build_kind == kind:
            g.build_kind = None

    def toggle_speed(self, *_):
        self.field.speed = 2 if self.field.speed == 1 else 1
        self.b_speed.text = f'x{self.field.speed}'

    # ----- обновление надписей -----
    def refresh(self):
        g = self.field.game
        m = g.mode
        lives = 'беск.' if m['endless'] else str(g.lives)
        wave = f"{g.wave}/{m['win_wave']}" if m['win_wave'] else str(g.wave)
        info = f"{m['name']}   Золото: {g.gold}   Жизни: {lives}   Волна: {wave}"
        t = g.selected
        if t:
            d = TOWERS[t.kind]
            info += f"   |   {d['name']} ур.{t.level}: урон {t.dmg:.0f}, радиус {t.range:.1f}"
        elif g.build_kind:
            d = TOWERS[g.build_kind]
            info += f"   |   {d['name']} ({d['hint']}): коснись свободной клетки"
        self.info_label.text = info

        for kind, b in self.tower_buttons.items():
            can = g.gold >= TOWERS[kind]['cost']
            b.background_color = (1, 1, 1, 1) if can else (0.5, 0.5, 0.5, 1)
            if g.build_kind is None and b.state == 'down':
                b.state = 'normal'

        if t:
            cost = t.upgrade_cost()
            if cost is None:
                self.b_up.text, self.b_up.disabled = 'Макс.\nуровень', True
            else:
                self.b_up.text, self.b_up.disabled = f'Улучшить\n{cost}', g.gold < cost
            self.b_sell.text, self.b_sell.disabled = f'Продать\n+{t.sell_value()}', False
        else:
            self.b_up.text, self.b_up.disabled = 'Улучшить', True
            self.b_sell.text, self.b_sell.disabled = 'Продать', True

        locked = g.wave_active and not m['overlap']
        if m['auto'] and g.wave > 0 and not g.game_over:
            self.b_wave.text = f"Волна {g.wave + 1}\nчерез {int(g.auto_timer) + 1} с"
            self.b_wave.disabled = False
        else:
            self.b_wave.disabled = locked or g.game_over
            self.b_wave.text = 'Идёт\nволна' if locked else f'Старт\nволна {g.wave + 1}'

        if g.game_over:
            if g.victory:
                head = f"ПОБЕДА!\nПройдено волн: {g.wave}"
            else:
                head = f"ИГРА ОКОНЧЕНА\nДостигнута волна: {g.wave}"
            self.msg.text = head + "\n\nКоснись экрана, чтобы сыграть ещё раз"
        else:
            self.msg.text = ''


class TowerDefenseApp(App):
    title = 'Tower Defense'

    def build(self):
        Clock.schedule_once(self.start_sound, 0.5)
        return Root()

    def start_sound(self, dt):
        try:
            SFX.init(self.user_data_dir)
        except Exception:
            pass  # без звука играть тоже можно

    def on_pause(self):
        return True


if __name__ == '__main__':
    TowerDefenseApp().run()
