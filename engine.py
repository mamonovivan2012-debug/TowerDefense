"""Игровая логика Tower Defense (чистый Python, без Kivy).

Все координаты — в клетках: клетка (col, row) занимает [col, col+1] x [row, row+1],
ряд 0 — нижний. Баланс настраивается константами ниже.
"""
import math
import random

COLS, ROWS = 14, 7

# Путь наземных врагов (центры клеток)
WAYPOINTS = [(-0.5, 5.5), (3.5, 5.5), (3.5, 1.5), (7.5, 1.5),
             (7.5, 5.5), (10.5, 5.5), (10.5, 2.5), (14.5, 2.5)]
# Летуны летят напрямую от входа к выходу
FLY_PATH = [WAYPOINTS[0], WAYPOINTS[-1]]
PATHS = {'ground': WAYPOINTS, 'fly': FLY_PATH}


def _path_cells():
    cells = set()
    for (x1, y1), (x2, y2) in zip(WAYPOINTS, WAYPOINTS[1:]):
        c1, c2 = sorted((math.floor(x1), math.floor(x2)))
        r1, r2 = sorted((math.floor(y1), math.floor(y2)))
        for c in range(c1, c2 + 1):
            for r in range(r1, r2 + 1):
                cells.add((c, r))
    return cells


def _remaining_table(path):
    """remain[i] — длина пути от точки i до выхода."""
    table = [0.0] * len(path)
    for i in range(len(path) - 2, -1, -1):
        table[i] = table[i + 1] + math.hypot(path[i + 1][0] - path[i][0],
                                             path[i + 1][1] - path[i][1])
    return table


PATH = _path_cells()
REMAIN = {k: _remaining_table(v) for k, v in PATHS.items()}

MAX_LEVEL = 3

# ---------- режимы игры ----------
_MODE_DEFAULTS = dict(gold=200, lives=20, hp=1.0, reward=1.0, growth=1.15,
                      win_wave=0, auto=0, overlap=False, endless=False,
                      waves='normal')

_MODE_LIST = [
    ('classic', dict(name='Классика',
                     desc='Бесконечные волны. Продержись как можно дольше.')),
    ('campaign', dict(name='Кампания', gold=250, growth=1.135, win_wave=30,
                      desc='Пройди 30 волн и победи. Финал — три босса.')),
    ('blitz', dict(name='Блиц', gold=300, lives=25, growth=1.15, auto=12,
                   overlap=True,
                   desc='Волны идут сами каждые 12 секунд. Не зевай!')),
    ('hardcore', dict(name='Хардкор', gold=150, lives=5, hp=1.3, reward=0.85,
                      desc='Всего 5 жизней, враги крепче, золота меньше.')),
    ('boss', dict(name='Босс-рейд', gold=300, growth=1.1, reward=1.25,
                  waves='boss',
                  desc='В каждой волне боссы, танки и целители.')),
    ('sandbox', dict(name='Песочница', gold=5000, lives=1, endless=True,
                     overlap=True,
                     desc='5000 золота, жизни не кончаются. Пробуй всё.')),
]
MODES = {key: dict(_MODE_DEFAULTS, **cfg) for key, cfg in _MODE_LIST}

# ---------- башни ----------
TOWERS = {
    'cannon': dict(name='Пушка', cost=50, range=2.6, dmg=9, cd=0.45,
                   color=(0.25, 0.7, 1.0), proj_speed=10,
                   hint='быстрая, универсальная'),
    'sniper': dict(name='Снайпер', cost=100, range=5.0, dmg=45, cd=1.6,
                   color=(0.95, 0.9, 0.3), proj_speed=20,
                   hint='дальний, мощный выстрел'),
    'ice': dict(name='Лёд', cost=75, range=2.3, dmg=3, cd=0.8,
                color=(0.55, 1.0, 1.0), proj_speed=9, slow=0.5, slow_t=1.5,
                hint='замедляет врагов'),
    'mortar': dict(name='Мортира', cost=125, range=3.4, dmg=22, cd=1.5,
                   color=(1.0, 0.5, 0.2), proj_speed=6, splash=1.0,
                   ground_only=True, hint='урон по площади, только по земле'),
}

# ---------- враги ----------
ENEMIES = {
    'grunt': dict(hp=30, speed=1.0, reward=6, leak=1, r=0.28,
                  color=(0.9, 0.25, 0.25)),
    'fast': dict(hp=20, speed=1.9, reward=7, leak=1, r=0.22,
                 color=(1.0, 0.85, 0.2)),
    'tank': dict(hp=140, speed=0.6, reward=16, leak=2, r=0.36,
                 color=(0.7, 0.35, 0.9)),
    'boss': dict(hp=900, speed=0.5, reward=120, leak=5, r=0.45,
                 color=(1.0, 0.4, 0.1)),
    # новые:
    'swarm': dict(hp=9, speed=1.5, reward=2, leak=1, r=0.16,
                  color=(1.0, 0.6, 0.75)),
    'armored': dict(hp=90, speed=0.8, reward=14, leak=2, r=0.32, armor=5,
                    color=(0.55, 0.6, 0.68)),
    'flyer': dict(hp=45, speed=1.3, reward=12, leak=2, r=0.26, fly=True,
                  color=(0.85, 0.9, 1.0)),
    'splitter': dict(hp=100, speed=0.8, reward=12, leak=1, r=0.34,
                     color=(0.65, 0.9, 0.2)),
    'healer': dict(hp=60, speed=0.9, reward=18, leak=1, r=0.27,
                   color=(0.2, 0.9, 0.6)),
}

HEAL_RADIUS = 1.6
HEAL_PERCENT = 0.08  # доля максимального здоровья в секунду


class Enemy:
    def __init__(self, kind, hp_mult=1.0, reward_mult=1.0):
        d = ENEMIES[kind]
        self.kind = kind
        self.hp_mult, self.reward_mult = hp_mult, reward_mult
        self.max_hp = self.hp = d['hp'] * hp_mult
        self.speed = d['speed']
        self.reward = max(1, int(d['reward'] * reward_mult))
        self.leak = d['leak']
        self.armor = d.get('armor', 0)
        self.fly = d.get('fly', False)
        self.color = d['color']
        self.r = d['r']
        self.route = 'fly' if self.fly else 'ground'
        self.path = PATHS[self.route]
        self.x, self.y = self.path[0]
        self.wp = 1
        self.slow = 1.0
        self.slow_t = 0.0
        self.heal_t = 1.0
        self.reached = False

    def remaining(self):
        """Сколько осталось до выхода (меньше — ближе к выходу)."""
        i = min(self.wp, len(self.path) - 1)
        tx, ty = self.path[i]
        return math.hypot(tx - self.x, ty - self.y) + REMAIN[self.route][i]

    def move(self, dt):
        speed = self.speed * (self.slow if self.slow_t > 0 else 1.0)
        self.slow_t = max(0.0, self.slow_t - dt)
        dist = speed * dt
        while dist > 0 and self.wp < len(self.path):
            tx, ty = self.path[self.wp]
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy)
            if d <= dist:
                self.x, self.y = tx, ty
                self.wp += 1
                dist -= d
            else:
                self.x += dx / d * dist
                self.y += dy / d * dist
                dist = 0
        if self.wp >= len(self.path):
            self.reached = True


class Tower:
    def __init__(self, kind, col, row):
        d = TOWERS[kind]
        self.kind, self.col, self.row = kind, col, row
        self.x, self.y = col + 0.5, row + 0.5
        self.range, self.dmg, self.cd = d['range'], d['dmg'], d['cd']
        self.ground_only = d.get('ground_only', False)
        self.timer = 0.0
        self.level = 1
        self.spent = d['cost']
        self.angle = 0.0

    def upgrade_cost(self):
        if self.level >= MAX_LEVEL:
            return None
        return int(TOWERS[self.kind]['cost'] * (0.7 if self.level == 1 else 1.0))

    def upgrade(self):
        self.level += 1
        self.dmg *= 1.7
        self.range *= 1.12
        self.cd *= 0.88

    def sell_value(self):
        return int(self.spent * 0.7)


class Bullet:
    def __init__(self, tower, target):
        d = TOWERS[tower.kind]
        self.x, self.y = tower.x, tower.y
        self.target = target
        self.tx, self.ty = target.x, target.y
        self.speed = d['proj_speed']
        self.dmg = tower.dmg
        self.splash = d.get('splash', 0)
        self.slow = d.get('slow', 0)
        self.slow_t = d.get('slow_t', 0)
        self.color = d['color']
        self.dead = False


class Game:
    def __init__(self):
        self.mode_key = 'classic'
        self.reset()

    def reset(self, mode_key=None):
        """Новая партия. Без аргумента — тот же режим."""
        if mode_key:
            self.mode_key = mode_key
        m = self.mode = MODES[self.mode_key]
        self.gold = m['gold']
        self.lives = m['lives']
        self.wave = 0
        self.wave_active = False
        self.spawners = []         # [очередь, таймер, пауза]; элемент очереди: (вид, hp*, награда*)
        self.auto_timer = 0.0
        self.enemies, self.towers, self.bullets = [], [], []
        self.flashes = []          # [x, y, радиус, время жизни, (r, g, b)]
        self.events = []           # названия звуков для интерфейса
        self.selected = None
        self.build_kind = None
        self.game_over = False
        self.victory = False

    def _emit(self, name):
        if len(self.events) < 300:
            self.events.append(name)

    # ---------- волны ----------
    def _build_wave(self, n):
        if self.mode['waves'] == 'boss':
            q = ['grunt'] * n + ['tank'] * (2 + n)
            if n >= 2:
                q += ['armored'] * (1 + n // 2)
            if n >= 3:
                q += ['healer'] * (1 + n // 5)
            if n >= 4:
                q += ['flyer'] * (n // 3)
            random.shuffle(q)
            for _ in range(1 + n // 4):
                q.insert(random.randint(len(q) // 4, len(q)), 'boss')
            return q, max(0.5, 1.1 - 0.02 * n)

        q = ['grunt'] * (4 + 2 * n)
        if n >= 3:
            q += ['fast'] * n
        if n >= 4:
            q += ['swarm'] * min(30, 2 * n)
        if n >= 5:
            q += ['tank'] * (n // 2)
        if n >= 6:
            q += ['armored'] * ((n - 2) // 2)
        if n >= 7:
            q += ['flyer'] * (n // 2 - 1)
        if n >= 8:
            q += ['splitter'] * ((n - 5) // 2)
        if n >= 9:
            q += ['healer'] * (1 + (n - 9) // 3)
        random.shuffle(q)
        if n % 10 == 0:
            q += ['boss'] * (n // 10)
        return q, max(0.35, 0.9 - 0.025 * n)

    def start_wave(self):
        if self.game_over:
            return
        if self.wave_active and not self.mode['overlap']:
            return
        self.wave += 1
        n = self.wave
        hp_mult = self.mode['hp'] * self.mode['growth'] ** (n - 1)
        reward_mult = self.mode['reward'] * (1 + 0.06 * (n - 1))
        queue, gap = self._build_wave(n)
        self.spawners.append([[(k, hp_mult, reward_mult) for k in queue], 0.0, gap])
        self.wave_active = True
        self.auto_timer = self.mode['auto']
        self._emit('wave')

    # ---------- действия игрока ----------
    def tap(self, col, row):
        """Касание клетки: выбрать башню или построить выбранный тип."""
        if not (0 <= col < COLS and 0 <= row < ROWS):
            self.selected = None
            return
        tower = next((t for t in self.towers if t.col == col and t.row == row), None)
        if tower:
            self.selected = tower
            self.build_kind = None
        elif (col, row) in PATH or not self.build_kind:
            self.selected = None
        else:
            cost = TOWERS[self.build_kind]['cost']
            if self.gold >= cost:
                self.gold -= cost
                self.towers.append(Tower(self.build_kind, col, row))
                self._emit('build')
            else:
                self._emit('deny')
            self.selected = None

    def upgrade_selected(self):
        t = self.selected
        if not t:
            return
        cost = t.upgrade_cost()
        if cost is not None and self.gold >= cost:
            self.gold -= cost
            t.spent += cost
            t.upgrade()
            self._emit('upgrade')
        else:
            self._emit('deny')

    def sell_selected(self):
        t = self.selected
        if not t:
            return
        self.gold += t.sell_value()
        self.towers.remove(t)
        self.selected = None
        self._emit('sell')

    # ---------- симуляция ----------
    def _target(self, t):
        best, best_rem = None, 1e18
        r2 = t.range ** 2
        for e in self.enemies:
            if t.ground_only and e.fly:
                continue
            if (e.x - t.x) ** 2 + (e.y - t.y) ** 2 <= r2:
                rem = e.remaining()
                if rem < best_rem:
                    best, best_rem = e, rem
        return best

    def _damage(self, e, b):
        e.hp -= max(1.0, b.dmg - e.armor)
        if b.slow:
            e.slow, e.slow_t = b.slow, b.slow_t

    def _hit(self, b):
        if b.splash:
            self._emit('explode')
            self.flashes.append([b.tx, b.ty, b.splash, 0.25, (1.0, 0.6, 0.2)])
            for e in self.enemies:
                if not e.fly and math.hypot(e.x - b.tx, e.y - b.ty) <= b.splash:
                    self._damage(e, b)
        elif b.target.hp > 0 and not b.target.reached:
            self._damage(b.target, b)

    def _heal(self, dt):
        for h in self.enemies:
            if h.kind != 'healer':
                continue
            h.heal_t -= dt
            if h.heal_t > 0:
                continue
            h.heal_t = 1.0
            healed = False
            for o in self.enemies:
                if (o is not h and o.hp < o.max_hp
                        and math.hypot(o.x - h.x, o.y - h.y) <= HEAL_RADIUS):
                    o.hp = min(o.max_hp, o.hp + o.max_hp * HEAL_PERCENT)
                    healed = True
            if healed:
                self._emit('heal')
                self.flashes.append([h.x, h.y, HEAL_RADIUS, 0.3, (0.3, 1.0, 0.5)])

    def update(self, dt):
        if self.game_over:
            return
        m = self.mode

        # автозапуск волн (Блиц)
        if m['auto'] and self.wave > 0:
            self.auto_timer -= dt
            if self.auto_timer <= 0:
                self.start_wave()

        # спавн и конец волны
        for sp in self.spawners:
            sp[1] -= dt
            if sp[0] and sp[1] <= 0:
                kind, hp_mult, reward_mult = sp[0].pop(0)
                self.enemies.append(Enemy(kind, hp_mult, reward_mult))
                sp[1] = sp[2]
        self.spawners = [sp for sp in self.spawners if sp[0]]
        if self.wave_active:
            if not self.spawners and not self.enemies:
                self.wave_active = False
                self.gold += 20 + 3 * self.wave
                if m['win_wave'] and self.wave >= m['win_wave']:
                    self.game_over = self.victory = True
                    self._emit('victory')
                    return
                self._emit('wave_clear')

        # враги
        for e in self.enemies:
            e.move(dt)
            if e.reached:
                self._emit('leak')
                if not m['endless']:
                    self.lives -= e.leak
        self.enemies = [e for e in self.enemies if not e.reached]
        if self.lives <= 0:
            self.lives = 0
            self.game_over = True
            self._emit('gameover')
            return

        self._heal(dt)

        # башни
        for t in self.towers:
            t.timer -= dt
            target = self._target(t)
            if target:
                t.angle = math.atan2(target.y - t.y, target.x - t.x)
                if t.timer <= 0:
                    t.timer = t.cd
                    self.bullets.append(Bullet(t, target))
                    self._emit('shoot_' + t.kind)

        # снаряды
        for b in self.bullets:
            if b.target.hp > 0 and not b.target.reached:
                b.tx, b.ty = b.target.x, b.target.y
            dx, dy = b.tx - b.x, b.ty - b.y
            d = math.hypot(dx, dy)
            step = b.speed * dt
            if d <= step:
                self._hit(b)
                b.dead = True
            else:
                b.x += dx / d * step
                b.y += dy / d * step
        self.bullets = [b for b in self.bullets if not b.dead]

        # убитые враги (делители рождают двух малышей)
        alive, born = [], []
        for e in self.enemies:
            if e.hp <= 0:
                self.gold += e.reward
                self._emit('kill')
                if e.kind == 'splitter':
                    for k in (-1, 1):
                        c = Enemy('swarm', e.hp_mult, e.reward_mult)
                        c.x, c.y, c.wp = e.x + 0.12 * k, e.y, e.wp
                        born.append(c)
            else:
                alive.append(e)
        self.enemies = alive + born

        # вспышки
        for f in self.flashes:
            f[3] -= dt
        self.flashes = [f for f in self.flashes if f[3] > 0]
