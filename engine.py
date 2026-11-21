"""Игровая логика Tower Defense (чистый Python, без Kivy).

Все координаты — в клетках: клетка (col, row) занимает [col, col+1] x [row, row+1],
ряд 0 — нижний. Баланс настраивается константами ниже.
"""
import math
import random

COLS, ROWS = 14, 7

# Путь врагов (центры клеток)
WAYPOINTS = [(-0.5, 5.5), (3.5, 5.5), (3.5, 1.5), (7.5, 1.5),
             (7.5, 5.5), (10.5, 5.5), (10.5, 2.5), (14.5, 2.5)]


def _path_cells():
    cells = set()
    for (x1, y1), (x2, y2) in zip(WAYPOINTS, WAYPOINTS[1:]):
        c1, c2 = sorted((math.floor(x1), math.floor(x2)))
        r1, r2 = sorted((math.floor(y1), math.floor(y2)))
        for c in range(c1, c2 + 1):
            for r in range(r1, r2 + 1):
                cells.add((c, r))
    return cells


PATH = _path_cells()

START_GOLD = 200
START_LIVES = 20
MAX_LEVEL = 3

TOWERS = {
    'cannon': dict(name='Пушка', cost=50, range=2.6, dmg=9, cd=0.45,
                   color=(0.25, 0.7, 1.0), proj_speed=10),
    'sniper': dict(name='Снайпер', cost=100, range=5.0, dmg=45, cd=1.6,
                   color=(0.95, 0.9, 0.3), proj_speed=20),
    'ice': dict(name='Лёд', cost=75, range=2.3, dmg=3, cd=0.8,
                color=(0.55, 1.0, 1.0), proj_speed=9, slow=0.5, slow_t=1.5),
    'mortar': dict(name='Мортира', cost=125, range=3.4, dmg=22, cd=1.5,
                   color=(1.0, 0.5, 0.2), proj_speed=6, splash=1.0),
}

ENEMIES = {
    'grunt': dict(hp=30, speed=1.0, reward=6, leak=1, r=0.28, color=(0.9, 0.25, 0.25)),
    'fast': dict(hp=20, speed=1.9, reward=7, leak=1, r=0.22, color=(1.0, 0.85, 0.2)),
    'tank': dict(hp=140, speed=0.6, reward=16, leak=2, r=0.36, color=(0.7, 0.35, 0.9)),
    'boss': dict(hp=900, speed=0.5, reward=120, leak=5, r=0.45, color=(1.0, 0.4, 0.1)),
}


class Enemy:
    def __init__(self, kind, wave):
        d = ENEMIES[kind]
        self.kind = kind
        self.max_hp = self.hp = d['hp'] * 1.15 ** (wave - 1)
        self.speed = d['speed']
        self.reward = int(d['reward'] * (1 + 0.06 * (wave - 1)))
        self.leak = d['leak']
        self.color = d['color']
        self.r = d['r']
        self.x, self.y = WAYPOINTS[0]
        self.wp = 1
        self.slow = 1.0
        self.slow_t = 0.0
        self.reached = False

    def progress(self):
        """Чем больше, тем дальше враг продвинулся по пути."""
        tx, ty = WAYPOINTS[min(self.wp, len(WAYPOINTS) - 1)]
        return self.wp * 1000 - math.hypot(tx - self.x, ty - self.y)

    def move(self, dt):
        speed = self.speed * (self.slow if self.slow_t > 0 else 1.0)
        self.slow_t = max(0.0, self.slow_t - dt)
        dist = speed * dt
        while dist > 0 and self.wp < len(WAYPOINTS):
            tx, ty = WAYPOINTS[self.wp]
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
        if self.wp >= len(WAYPOINTS):
            self.reached = True


class Tower:
    def __init__(self, kind, col, row):
        d = TOWERS[kind]
        self.kind, self.col, self.row = kind, col, row
        self.x, self.y = col + 0.5, row + 0.5
        self.range, self.dmg, self.cd = d['range'], d['dmg'], d['cd']
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
        self.reset()

    def reset(self):
        self.gold = START_GOLD
        self.lives = START_LIVES
        self.wave = 0
        self.wave_active = False
        self.spawn_queue = []
        self.spawn_timer = 0.0
        self.spawn_gap = 0.9
        self.enemies, self.towers, self.bullets, self.flashes = [], [], [], []
        self.selected = None
        self.build_kind = None
        self.game_over = False

    # ---------- действия игрока ----------
    def start_wave(self):
        if self.wave_active or self.game_over:
            return
        self.wave += 1
        n = self.wave
        q = ['grunt'] * (5 + 2 * n)
        if n >= 3:
            q += ['fast'] * n
        if n >= 5:
            q += ['tank'] * (n // 2)
        random.shuffle(q)
        if n % 10 == 0:
            q.append('boss')
        self.spawn_queue = q
        self.spawn_gap = max(0.35, 0.9 - 0.025 * n)
        self.spawn_timer = 0.0
        self.wave_active = True

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

    def sell_selected(self):
        t = self.selected
        if not t:
            return
        self.gold += t.sell_value()
        self.towers.remove(t)
        self.selected = None

    # ---------- симуляция ----------
    def _target(self, t):
        best, best_p = None, -1e18
        r2 = t.range ** 2
        for e in self.enemies:
            if (e.x - t.x) ** 2 + (e.y - t.y) ** 2 <= r2:
                p = e.progress()
                if p > best_p:
                    best, best_p = e, p
        return best

    def _damage(self, e, b):
        e.hp -= b.dmg
        if b.slow:
            e.slow, e.slow_t = b.slow, b.slow_t

    def _hit(self, b):
        if b.splash:
            self.flashes.append([b.tx, b.ty, b.splash, 0.25])
            for e in self.enemies:
                if math.hypot(e.x - b.tx, e.y - b.ty) <= b.splash:
                    self._damage(e, b)
        elif b.target.hp > 0 and not b.target.reached:
            self._damage(b.target, b)

    def update(self, dt):
        if self.game_over:
            return

        # спавн и конец волны
        if self.wave_active:
            self.spawn_timer -= dt
            if self.spawn_queue and self.spawn_timer <= 0:
                self.enemies.append(Enemy(self.spawn_queue.pop(0), self.wave))
                self.spawn_timer = self.spawn_gap
            elif not self.spawn_queue and not self.enemies:
                self.wave_active = False
                self.gold += 20 + 3 * self.wave

        # враги
        for e in self.enemies:
            e.move(dt)
            if e.reached:
                self.lives -= e.leak
        self.enemies = [e for e in self.enemies if not e.reached]
        if self.lives <= 0:
            self.lives = 0
            self.game_over = True
            return

        # башни
        for t in self.towers:
            t.timer -= dt
            target = self._target(t)
            if target:
                t.angle = math.atan2(target.y - t.y, target.x - t.x)
                if t.timer <= 0:
                    t.timer = t.cd
                    self.bullets.append(Bullet(t, target))

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

        # убитые враги
        alive = []
        for e in self.enemies:
            if e.hp <= 0:
                self.gold += e.reward
            else:
                alive.append(e)
        self.enemies = alive

        # вспышки взрывов
        for f in self.flashes:
            f[3] -= dt
        self.flashes = [f for f in self.flashes if f[3] > 0]
