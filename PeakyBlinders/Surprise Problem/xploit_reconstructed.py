"""
xploit.py - Reconstructed from xdis bytecode disassembly
A Pygame dungeon platformer with 6 deliberately broken stages.

Constants:
  _W=960, _H=600, _F=60, _T=40
  Colors: c0..c11
  _GI=-0.5 (gravity inverted), _GN=0.5 (gravity normal)
  _SEED=0xDEADBEEF, _XK=85
  _MAGIC=_SEED ^ 0xCAFEBABE
  _UNLK=0xC0FFEE, _CKSUM=sum(_UNLK.to_bytes(3,'big'))
"""

import pygame
import sys
import math
import random

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
_W = 960
_H = 600
_F = 60
_T = 40

c0  = (0, 0, 0)
c1  = (255, 255, 255)
c2  = (80, 80, 80)
c3  = (40, 40, 40)
c4  = (220, 50, 50)
c5  = (50, 200, 80)
c6  = (50, 100, 220)
c7  = (255, 210, 0)
c8  = (255, 140, 0)
c9  = (0, 220, 220)
c10 = (160, 60, 200)
c11 = (140, 20, 20)

_GI = -0.5   # gravity inverted (upward)
_GN = 0.5    # gravity normal (downward)

_SEED  = int.from_bytes(b'\xde\xad\xbe\xef', 'big')  # 3735928559
_XK    = 85
_MAGIC = _SEED ^ 3405691582                            # _SEED ^ 0xCAFEBABE
_UNLK  = 12648430                                       # 0xC0FFEE
_CKSUM = sum(_UNLK.to_bytes(3, 'big'))

_qt = pygame.time.get_ticks   # shorthand for get_ticks

# ---------------------------------------------------------------------------
# _xb: XOR-obfuscated byte helper (module level)
# bytes(b ^ ((k + i) % 256) for i, b in enumerate(data))
# ---------------------------------------------------------------------------
# (used in _scr_t / _scr_w / _scr_r for label decoding)

# ---------------------------------------------------------------------------
# Font helper
# ---------------------------------------------------------------------------
def _sf():
    return pygame.font.SysFont(None, 20)

# ---------------------------------------------------------------------------
# Helper: draw text on surface
# ---------------------------------------------------------------------------
def _ht(s, txt, x, y, col, ctr=False, sz=20):
    """Render text onto surface s at (x, y) with optional centering."""
    f = pygame.font.SysFont(None, sz)
    ts = f.render(str(txt), True, col)
    if ctr:
        x = x - ts.get_width() // 2
    s.blit(ts, (x, y))

# ---------------------------------------------------------------------------
# Label globals (decoded from XOR-obfuscated byte tuples at module level)
# ---------------------------------------------------------------------------
_LBL_G = "XPLOIT"   # game window caption (decoded from obfuscated bytes)

# ---------------------------------------------------------------------------
# _validate_env
# ---------------------------------------------------------------------------
def _validate_env():
    """Returns True if checksum passes, False otherwise."""
    return (_CKSUM ^ (_MAGIC & 255)) == 0

# ---------------------------------------------------------------------------
# _PV = _Zv() -- the global validator instance
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Screen functions (title, round-clear, win)
# ---------------------------------------------------------------------------
def _scr_t(s, cl):
    """Title screen -- waits for RETURN key."""
    while True:
        cl.tick(_F)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
                return
        s.fill(c0)
        _ht(s, _LBL_G, _W // 2, _H // 2 - 60, c7, ctr=True, sz=72)
        _ht(s, "Press ENTER", _W // 2, _H // 2 + 20, c1, ctr=True)
        pygame.display.flip()

def _scr_r(s, cl, nm):
    """Round-clear screen -- shows stage name, waits for RETURN."""
    while True:
        cl.tick(_F)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
                return
        s.fill(c0)
        _ht(s, nm, _W // 2, _H // 2 - 30, c5, ctr=True, sz=36)
        _ht(s, "Press ENTER", _W // 2, _H // 2 + 20, c1, ctr=True)
        pygame.display.flip()

def _scr_w(s, cl):
    """Win screen -- shows congratulations, waits for RETURN then exits."""
    while True:
        cl.tick(_F)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
                return
        s.fill(c0)
        _ht(s, "YOU WIN!", _W // 2, _H // 2 - 30, c7, ctr=True, sz=48)
        _ht(s, "Press ENTER to exit", _W // 2, _H // 2 + 30, c1, ctr=True)
        pygame.display.flip()


# ===========================================================================
# _Zv  --  Validator class
# ===========================================================================
class _Zv:
    _LK = 0

    def __init__(self):
        self._tk = _qt()
        self._ac = False

    def _ck(self):
        """Returns (current_ticks - self._tk) % 256."""
        return (_qt() - self._tk) % 256

    def _ev(self, x):
        """Check if (x & 255) == 66."""
        return (x & 255) == 66

    @staticmethod
    def _rs(v):
        """XOR v with (_XK & 255)."""
        return v ^ (_XK & 255)


_PV = _Zv()


# ===========================================================================
# _Eq  --  Player entity
# ===========================================================================
class _Eq:
    _SW, _SH = 30, 36

    def __init__(self, x, y):
        self.r  = pygame.Rect(x, y, self._SW, self._SH)
        self.vx = 0.0
        self.vy = 0.0
        self.og = False          # on ground
        self.cn = 0              # collectible count
        self.hp = 3
        self.al = True           # alive
        self.gv = _GN            # gravity value (default normal = 0.5)
        self.jp = 12.7           # jump power
        self.sp = 5              # speed
        self.bl = []             # bullet list
        self.sc = 0              # shoot cooldown

    # -- movement: normal (K_LEFT / K_RIGHT / K_UP) -------------------------
    def _mi(self, k):
        self.vx = 0
        if k[pygame.K_LEFT]:
            self.vx = -self.sp
        if k[pygame.K_RIGHT]:
            self.vx = self.sp
        if k[pygame.K_UP]:
            if self.og:
                self.vy = -self.jp
                self.og = False
            return
        return

    # -- movement: inverted (K_LEFT / K_RIGHT / K_DOWN) ---------------------
    def _mj(self, k):
        """
        Movement handler for inverted-gravity stages.
        BUG (Stage 5): LEFT sets vx = +sp (moves right),
                        RIGHT sets vx = -sp (moves left).
        Controls are swapped!
        """
        self.vx = 0
        if k[pygame.K_LEFT]:
            self.vx = self.sp       # BUG: should be -self.sp (LEFT should go left)
        if k[pygame.K_RIGHT]:
            self.vx = -self.sp      # BUG: should be +self.sp (RIGHT should go right)
        if k[pygame.K_DOWN]:
            if self.og:
                self.vy = self.jp    # jump "down" (which is up with inverted gravity)
                self.og = False
            return
        return

    # -- fire / shoot -------------------------------------------------------
    def _fs(self, k):
        self.sc = max(0, self.sc - 1)
        if k[pygame.K_SPACE] and self.sc == 0:
            self.bl.append(_Fx(self.r.centerx, self.r.centery, 1))
            self.sc = 20

    # -- apply physics (gravity + movement + collisions) --------------------
    def _ap(self, pf):
        self.vy += self.gv
        self.r.x += int(self.vx)
        self._cx(pf)
        self.r.y += int(self.vy)
        self._cy(pf)

    # -- horizontal collision -----------------------------------------------
    def _cx(self, pf):
        for p in pf:
            if self.r.colliderect(p):
                if self.vx > 0:
                    self.r.right = p.left
                else:
                    self.r.left = p.right
                self.vx = 0

    # -- vertical collision -------------------------------------------------
    def _cy(self, pf):
        self.og = False
        for p in pf:
            if self.r.colliderect(p):
                if self.vy > 0:
                    # falling down, landed on top
                    self.r.bottom = p.top
                    self.vy = 0
                    if self.gv >= 0:
                        self.og = True
                elif self.vy < 0:
                    # moving up, hit ceiling
                    self.r.top = p.bottom
                    self.vy = 0
                    if self.gv < 0:
                        self.og = True

    # -- clamp position -----------------------------------------------------
    def _ck(self):
        self.r.x = max(0, min(self.r.x, _W - self._SW))
        self.r.y = max(-200, min(self.r.y, _H + 200))

    # -- draw player --------------------------------------------------------
    def _v(self, s):
        # body
        pygame.draw.rect(s, c6, self.r)
        pygame.draw.rect(s, c9, self.r, 2)
        # eyes
        ex = self.r.x + 7
        ey = self.r.y + 8
        pygame.draw.circle(s, c1, (ex, ey), 5)
        pygame.draw.circle(s, c1, (ex + 14, ey), 5)
        # pupils
        pygame.draw.circle(s, c0, (ex + 2, ey), 2)
        pygame.draw.circle(s, c0, (ex + 16, ey), 2)


# ===========================================================================
# _Fx  --  Bullet / Projectile
# ===========================================================================
class _Fx:
    def __init__(self, x, y, d):
        self.r  = pygame.Rect(x, y, 10, 6)
        self.vx = 12 * d
        self.ac = True      # active

    def _u(self):
        self.r.x += self.vx
        if self.r.right < 0 or self.r.left > _W:
            self.ac = False

    def _v(self, s):
        pygame.draw.rect(s, c7, self.r)
        pygame.draw.rect(s, c8, self.r, 1)


# ===========================================================================
# _Rx  --  Collectible (coin)
# ===========================================================================
class _Rx:
    _R = 10   # radius

    def __init__(self, x, y):
        self.r  = pygame.Rect(x - self._R, y - self._R,
                              self._R * 2, self._R * 2)
        self.cd = False   # collected

    def _v(self, s):
        if not self.cd:
            pygame.draw.circle(s, c7, self.r.center, self._R)
            pygame.draw.circle(s, c8, self.r.center, self._R, 2)


# ===========================================================================
# _Ox  --  Door / Exit
# ===========================================================================
class _Ox:
    def __init__(self, x, y):
        self.r   = pygame.Rect(x, y, _T, _T * 2)
        self.op  = False    # open?
        self._pc = 0        # required collectible count

    def _c(self, p):
        """Check if player has enough collectibles to open."""
        self._pc = p.cn
        if p.cn >= 9999:       # BUG (Stage 1): threshold is 9999, but only 3 collectibles exist!
            self.op = True

    def _v(self, s):
        # draw door rect: green if open, red if locked
        pygame.draw.rect(s, c5 if self.op else c4, self.r)
        pygame.draw.rect(s, c1, self.r, 2)
        # keyhole if locked
        if not self.op:
            pygame.draw.circle(s, c7,
                               (self.r.right - 8, self.r.centery), 5)
        # label
        lbl = _sf().render(
            "".join(chr(c) for c in ([79,80,69,78] if self.op else [76,79,67,75,69,68])),
            True, c1)
        s.blit(lbl, (self.r.x, self.r.y - 20))


# ===========================================================================
# _Tx  --  Trap / Hazard (exit marker -- green EXIT box)
# ===========================================================================
class _Tx:
    def __init__(self, x, y):
        self.r = pygame.Rect(x, y, _T, _T)

    def _v(self, s):
        pygame.draw.rect(s, c5, self.r)
        pygame.draw.rect(s, c1, self.r, 2)
        # "EXIT" label
        s.blit(
            _sf().render(
                "".join(chr(c) for c in (69, 88, 73, 84)),  # "EXIT"
                True, c0),
            (self.r.x + 4, self.r.y + 12))


# ===========================================================================
# _Ux  --  Moving hazard (teleporting obstacle with pulsing color)
# ===========================================================================
class _Ux:
    def __init__(self, x, y):
        self.r   = pygame.Rect(x, y, _T, _T)
        self._tm = 0

    def _u(self, p):
        """If player gets within 50px, teleport to random location."""
        if math.hypot(p.r.centerx - self.r.centerx,
                      p.r.centery - self.r.centery) < 50:
            self.r.x = random.randint(60, _W - 100)
            self.r.y = random.randint(60, _H - 160)

    def _v(self, s):
        self._tm += 1
        g = abs(math.sin(self._tm * 0.05)) * 80
        # pulsing color
        pygame.draw.rect(s, (50, int(150 + g), 80), self.r)
        pygame.draw.rect(s, c1, self.r, 2)
        # "EXIT" label
        s.blit(
            _sf().render(
                "".join(chr(c) for c in (69, 88, 73, 84)),  # "EXIT"
                True, c0),
            (self.r.x + 4, self.r.y + 12))


# ===========================================================================
# _Gx  --  Enemy / Ghost (boss)
# ===========================================================================
class _Gx:
    _SW, _SH = 60, 60
    _MX = 10     # max HP

    def __init__(self, x, y):
        self.r  = pygame.Rect(x, y, self._SW, self._SH)
        self.mh = self._MX
        self.hp = self._MX
        self.vx = 3
        self.dd = False   # dead

    def _td(self, n):
        """Take damage.
        BUG (Stage 4): After subtracting damage, hp is immediately
        reset to self.mh (max health). The enemy can NEVER die!
        """
        self.hp -= n
        self.hp = self.mh  # BUG: resets hp back to max health!

    def _u(self, pf):
        """Update: move horizontally, apply simple gravity, check death."""
        self.r.x += self.vx
        # bounce off walls
        if self.r.right >= _W or self.r.left <= 0:
            self.vx *= -1
        # simple gravity (fall at 4 px/frame)
        self.r.y += 4
        for p in pf:
            if self.r.colliderect(p):
                self.r.bottom = p.top
        # check death
        if self.hp <= 0:
            self.dd = True

    def _v(self, s):
        if self.dd:
            return
        # draw body
        pygame.draw.rect(s, c11, self.r)
        pygame.draw.rect(s, c4, self.r, 3)
        # health bar
        bw = self._SW
        hw = int(bw * self.hp / self.mh)
        pygame.draw.rect(s, c3, (self.r.x, self.r.y - 14, bw, 10))
        pygame.draw.rect(s, c4, (self.r.x, self.r.y - 14, hw, 10))
        pygame.draw.rect(s, c1, (self.r.x, self.r.y - 14, bw, 10), 1)
        # "BOSS" label
        s.blit(
            _sf().render(
                "".join(chr(c) for c in (66, 79, 83, 83)),  # "BOSS"
                True, c1),
            (self.r.x + 6, self.r.y + 20))


# ===========================================================================
# _Mx  --  Base map / stage class
# ===========================================================================
class _Mx:
    def __init__(self):
        self.pf = []        # platforms list
        self.cp = False     # stage complete

    def _bg(self):
        """Build ground: full-width platform at bottom."""
        self.pf.append(pygame.Rect(0, _H - _T, _W, _T))

    def _dp(self, s):
        """Draw platforms."""
        for p in self.pf:
            pygame.draw.rect(s, c2, p)
            pygame.draw.rect(s, c3, p, 2)

    def _db(self, s, col=c3):
        """Draw background (fill with color)."""
        s.fill(col)


# ===========================================================================
# _S1  --  Stage 1: Collect coins & reach door
# ===========================================================================
class _S1(_Mx):
    _NM = "".join(chr(c) for c in (83, 116, 97, 103, 101, 32, 49))  # "Stage 1"

    def __init__(self, p):
        super().__init__()
        # place player
        p.r.topleft = (60, _H - _T - p._SH)
        p.cn = 0
        # build ground
        self._bg()
        # platforms
        for x, y in ((200, 420), (360, 350), (520, 280), (680, 350)):
            self.pf.append(pygame.Rect(x, y, 120, _T))
        # collectibles (3 coins)
        self.cv = [_Rx(240, 400), _Rx(400, 330), _Rx(560, 260)]
        # door (exit) -- requires collecting coins to open
        self.dv = _Ox(820, _H - _T - _T * 2)
        # BUG: _Ox._c checks p.cn >= 9999 to open the door,
        # but only 3 collectibles exist. Door can NEVER open!

    def _u(self, p, ev):
        k = pygame.key.get_pressed()
        p._mi(k)
        p._ap(self.pf)
        p._ck()
        # collect coins
        for c in self.cv:
            if not c.cd and p.r.colliderect(c.r):
                c.cd = True
                p.cn += 1
        # update door
        self.dv._c(p)
        # check if player enters open door
        if self.dv.op and p.r.colliderect(self.dv.r):
            self.cp = True
        # respawn if fallen
        if p.r.top > _H + 100:
            p.r.topleft = (60, _H - _T - p._SH)
            p.vy = 0

    def _v(self, s):
        self._db(s, (20, 20, 35))
        self._dp(s)
        for c in self.cv:
            c._v(s)
        self.dv._v(s)

    def _n(self, s, p):
        _ht(s, f"{p.cn}", 10, 10, c7, sz=20)
        _ht(s, self._NM, _W // 2, 10, c1, ctr=True)


# ===========================================================================
# _S2  --  Stage 2: Timed obstacle course
# ===========================================================================
class _S2(_Mx):
    _NM  = "".join(chr(c) for c in (83, 116, 97, 103, 101, 32, 50))  # "Stage 2"
    _SP  = 2    # BUG: player speed is set to 2 (very slow!) instead of normal 5
    _OBS = [(115, 26, 120), (190, 26, 148), (265, 26, 108),
            (340, 26, 155), (415, 26, 132), (490, 26, 146),
            (565, 26, 112), (640, 26, 150), (715, 26, 125),
            (790, 26, 153), (855, 26, 118)]

    def __init__(self, p):
        super().__init__()
        p.r.topleft = (40, _H - _T - p._SH)
        p.cn = 0
        p.sp = self._SP   # BUG: overrides player speed to 2
        # build ground
        self._bg()
        # obstacle pillars
        for ox, ow, oh in self._OBS:
            self.pf.append(pygame.Rect(ox, _H - _T - oh, ow, oh))
        # exit trap (green EXIT box) at far right
        self.xb = _Tx(905, _H - _T - _T)
        # timer
        self.st = _qt()
        self.ts = 5        # time limit in seconds
        self.go = False     # game-over flag

    def _tl(self):
        """Time left."""
        return self.ts - (_qt() - self.st) / 1000.0

    def _u(self, p, ev):
        p.sp = self._SP   # BUG: continuously overrides speed to 2
        if self.go:
            return
        if self._tl() <= 0:
            self._tgo()
        k = pygame.key.get_pressed()
        p._mi(k)
        p._ap(self.pf)
        p._ck()
        # respawn if fallen
        if p.r.top > _H + 100:
            p.r.topleft = (40, _H - _T - p._SH)
            p.vy = 0
        # check exit
        if p.r.colliderect(self.xb.r):
            self.cp = True

    def _tgo(self):
        """Time's up -- set game over."""
        self.go = True

    def _v(self, s):
        self._db(s, (20, 30, 20))
        # draw platforms
        for q in self.pf:
            pygame.draw.rect(s, c2, q)
            pygame.draw.rect(s, c3, q, 2)
        # draw exit
        self.xb._v(s)
        # game-over overlay
        if self.go:
            ov = pygame.Surface((_W, _H), pygame.SRCALPHA)
            ov.fill((180, 0, 0, 160))
            s.blit(ov, (0, 0))
            # "TERMINATED"
            _ht(s, "".join(chr(c) for c in (84,69,82,77,73,78,65,84,69,68)),
                 _W // 2, _H // 2, c1, ctr=True, sz=42)
            # "PATCH AND RETRY"
            _ht(s, "".join(chr(c) for c in (80,65,84,67,72,32,65,78,68,32,82,69,84,82,89)),
                 _W // 2, _H // 2 + 50, c7, ctr=True, sz=22)

    def _n(self, s, p):
        t  = max(0.0, self._tl())
        cl = c4 if t < 2 else (c7 if t < 4 else c5)
        _ht(s, f"{t:.2f}", _W // 2, 10, cl, ctr=True, sz=32)
        # progress bar
        prog = min(1.0, max(0.0, (p.r.x - 40) / 865))
        pygame.draw.rect(s, c3, (10, _H - 22, 200, 8))
        pygame.draw.rect(s, c5, (10, _H - 22, int(200 * prog), 8))
        pygame.draw.rect(s, c1, (10, _H - 22, 200, 8), 1)
        # stage name
        _ht(s, self._NM, _W // 2, _H - 28, c1, ctr=True)


# ===========================================================================
# _S3  --  Stage 3: Pit / Void stage (fall into pit = reset)
# ===========================================================================
class _S3(_Mx):
    _NM  = "".join(chr(c) for c in (83, 116, 97, 103, 101, 32, 51))  # "Stage 3"
    _SCY = _H - 239    # ceiling Y  (= 361)
    _PL, _PR = 150, 820  # pit left, pit right

    def __init__(self, p):
        super().__init__()
        p.r.topleft = (40, _H - _T - p._SH)
        p.cn = 0
        # left ground (0 to _PL)
        self.pf.append(pygame.Rect(0, _H - _T, self._PL, _T))
        # right ground (_PR to _W)
        self.pf.append(pygame.Rect(self._PR, _H - _T,
                                   _W - self._PR, _T))
        # elevated platform
        self.pf.append(pygame.Rect(self._PR + 30,
                                   _H - _T * 4, 120, _T))
        # breakable bridge pieces
        self.bp = []
        # exit
        self.xb = _Tx(self._PR + 60, _H - _T * 5)

    def _rdb(self):
        """Rebuild bridge: creates breakable blocks across the pit."""
        by = _H - _T
        for bx in range(self._PL, self._PR, 40):
            self.bp.append(pygame.Rect(bx, by - _T, 42, _T))
        self.pf.extend(self.bp)

    def _u(self, p, ev):
        k = pygame.key.get_pressed()
        p._mi(k)
        p._ap(self.pf)
        p._ck()
        # BUG: Check if player touches the ceiling (y <= _SCY).
        # If so, reset position. This invisible ceiling at y=361 prevents
        # the player from jumping high enough to reach the elevated platform
        # and exit at _H - _T*5 = 400. The ceiling resets them before they
        # can get there!
        if p.r.top <= self._SCY:
            p.r.topleft = (40, _H - _T - p._SH)
            p.vy = 0
        # respawn if fallen
        if p.r.top > _H + 100:
            p.r.topleft = (40, _H - _T - p._SH)
            p.vy = 0
        # check exit
        if p.r.colliderect(self.xb.r):
            self.cp = True

    def _v(self, s):
        self._db(s, (10, 10, 25))
        # ceiling
        ceil_rect = pygame.Rect(0, 0, _W, self._SCY)
        pygame.draw.rect(s, c3, ceil_rect)
        # stalactites
        sw = 24
        for sx in range(0, _W, sw):
            pts = [(sx, self._SCY),
                   (sx + sw // 2, self._SCY + 18),
                   (sx + sw, self._SCY)]
            pygame.draw.polygon(s, c4, pts)
            pygame.draw.polygon(s, c11, pts, 1)
        # draw platforms
        self._dp(s)
        # breakable bridge
        for b in self.bp:
            pygame.draw.rect(s, (139, 90, 43), b)
            pygame.draw.rect(s, (200, 140, 60), b, 2)
        # void pit (black rect)
        pygame.draw.rect(s, c0,
                         pygame.Rect(self._PL, _H - _T,
                                     self._PR - self._PL, _T))
        # "VOID" label
        vl = _sf().render(
            "".join(chr(c) for c in (86, 79, 73, 68)),  # "VOID"
            True, (50, 50, 50))
        s.blit(vl,
               ((self._PL + self._PR) // 2 - vl.get_width() // 2,
                _H - _T + 8))
        # exit
        self.xb._v(s)

    def _n(self, s, p):
        _ht(s, self._NM, _W // 2, 10, c1, ctr=True)


# ===========================================================================
# _S4  --  Stage 4: Boss fight
# ===========================================================================
class _S4(_Mx):
    _NM = "".join(chr(c) for c in (83, 116, 97, 103, 101, 32, 52))  # "Stage 4"

    def __init__(self, p):
        super().__init__()
        p.r.topleft = (60, _H - _T - p._SH)
        p.cn = 0
        p.bl.clear()
        # build ground
        self._bg()
        # platforms
        self.pf.append(pygame.Rect(100, _H - _T * 4, 200, _T))
        self.pf.append(pygame.Rect(400, _H - _T * 6, 200, _T))
        # boss enemy
        self.bx = _Gx(700, _H - _T - _Gx._SH)
        # exit (only accessible after boss is dead)
        self.xb = _Tx(870, _H - _T - _T)

    def _u(self, p, ev):
        k = pygame.key.get_pressed()
        p._mi(k)
        p._fs(k)         # shooting enabled in this stage
        p._ap(self.pf)
        p._ck()
        # update bullets
        for b in p.bl:
            b._u()
        # filter dead bullets
        p.bl = [b for b in p.bl if b.ac]
        # boss logic
        if not self.bx.dd:
            self.bx._u(self.pf)
            # bullet-boss collision
            for b in p.bl:
                if b.ac and b.r.colliderect(self.bx.r):
                    self.bx._td(1)   # BUG: _td resets hp to max -- boss is invincible!
                    b.ac = False
            # boss-player collision resets player
            if self.bx.r.colliderect(p.r):
                p.r.topleft = (60, _H - _T - p._SH)
                p.vy = 0
        # respawn if fallen
        if p.r.top > _H + 100:
            p.r.topleft = (60, _H - _T - p._SH)
            p.vy = 0
        # exit only accessible if boss dead
        if self.bx.dd:
            if p.r.colliderect(self.xb.r):
                self.cp = True

    def _v(self, s):
        self._db(s, (30, 10, 10))
        self._dp(s)
        self.bx._v(s)
        self.xb._v(s)

    def _n(self, s, p):
        _ht(s, "[SPC]", 10, 10, c9, sz=16)
        _ht(s, self._NM, _W // 2, 10, c1, ctr=True)
        if self.bx.dd:
            _ht(s,
                 "".join(chr(c) for c in (80,82,79,67,69,69,68)),  # "PROCEED"
                 _W // 2, _H // 2 - 40, c5, ctr=True, sz=26)


# ===========================================================================
# _S5  --  Stage 5: Inverted gravity
# ===========================================================================
class _S5(_Mx):
    _NM = "".join(chr(c) for c in (83, 116, 97, 103, 101, 32, 53))  # "Stage 5"

    def __init__(self, p):
        super().__init__()
        p.gv = _GI   # BUG: Sets gravity to _GI = -0.5 (inverted gravity, player floats UP)
        # place player near top (since gravity is inverted)
        p.r.topleft = (60, _T + 4)
        # ceiling platform (at y=0)
        self.pf.append(pygame.Rect(0, 0, _W, _T))
        # floor platform
        self.pf.append(pygame.Rect(0, _H - _T, _W, _T))
        # mid-air platforms
        for x, y in ((200, _T + 10), (380, _T + 60),
                      (560, _T + 20), (740, _T + 80)):
            self.pf.append(pygame.Rect(x, y, 120, _T))
        # moving hazard (teleports away when you get close)
        self.wx = _Ux(700, _T + 4)

    def _u(self, p, ev):
        p.gv = _GI   # BUG: Continuously forces inverted gravity
        k = pygame.key.get_pressed()
        p._mj(k)      # BUG: Uses _mj (inverted controls: LEFT=right, RIGHT=left)
        p._ap(self.pf)
        p._ck()
        # update moving hazard
        self.wx._u(p)
        # check if player has fallen off bottom (past floor)
        if p.r.bottom > _H - _T:
            p.r.topleft = (60, _T + 4)
            p.vy = 0
        # check exit (touching the moving hazard = win)
        if p.r.colliderect(self.wx.r):
            self.cp = True
            # BUG: But _Ux._u teleports away when player gets within 50px!
            # The exit condition requires touching a target that actively
            # avoids you. Combined with inverted controls, this is extremely
            # difficult.

    def _v(self, s):
        s.fill((15, 5, 30))
        # vertical grid lines
        for i in range(0, _W, 80):
            pygame.draw.line(s, (30, 10, 60), (i, 0), (i, _H))
        # horizontal grid lines
        for j in range(0, _H, 60):
            pygame.draw.line(s, (30, 10, 60), (0, j), (_W, j))
        # platforms
        self._dp(s)
        # moving hazard
        self.wx._v(s)
        # arrow decorations at bottom
        for ax in range(80, _W, 160):
            pygame.draw.polygon(s, (80, 0, 80),
                                [(ax, _H - 80),
                                 (ax - 15, _H - 50),
                                 (ax + 15, _H - 50)])

    def _n(self, s, p):
        _ht(s, self._NM, _W // 2, _H - 28, c1, ctr=True)


# ===========================================================================
# _S6  --  Stage 6: Maze with invisible walls
# ===========================================================================
class _S6(_Mx):
    _NM = "".join(chr(c) for c in (83, 116, 97, 103, 101, 32, 54))  # "Stage 6"
    _BX, _BY, _BW, _BH = 330, 140, 300, 270    # box region
    _WT = 40                                      # wall thickness

    def __init__(self, p):
        super().__init__()
        p.r.topleft = (60, _H - _T - p._SH)
        # build ground
        self._bg()
        # two elevated platforms
        self.pf.append(pygame.Rect(80, _H - _T * 4, 160, _T))
        self.pf.append(pygame.Rect(720, _H - _T * 4, 160, _T))
        # invisible box walls -- 4 walls forming a box
        self._bw = []
        for rx, ry, rw, rh in (
            # top wall
            (self._BX, self._BY, self._BW, self._WT),
            # bottom wall
            (self._BX, self._BY + self._BH - self._WT, self._BW, self._WT),
            # left wall
            (self._BX, self._BY, self._WT, self._BH),
            # right wall
            (self._BX + self._BW - self._WT, self._BY, self._WT, self._BH),
        ):
            q = pygame.Rect(rx, ry, rw, rh)
            self._bw.append(q)
            self.pf.append(q)
        # exit
        self.xb = _Tx(460, 255)
        # BUG: The exit at (460, 255) is INSIDE the invisible box
        # (box spans x:330-630, y:140-410). The box walls are added
        # to self.pf as collision platforms, trapping the player.
        # There is no gap in the box walls, so the exit is unreachable!

    def _u(self, p, ev):
        k = pygame.key.get_pressed()
        p._mi(k)
        p._ap(self.pf)
        p._ck()
        # respawn if fallen
        if p.r.top > _H + 100:
            p.r.topleft = (60, _H - _T - p._SH)
            p.vy = 0
        # check exit
        if p.r.colliderect(self.xb.r):
            self.cp = True

    def _v(self, s):
        self._db(s, (8, 8, 18))
        # vertical grid lines
        for i in range(0, _W, 120):
            pygame.draw.line(s, (18, 18, 35), (i, 0), (i, _H))
        # horizontal grid lines
        for j in range(0, _H, 90):
            pygame.draw.line(s, (18, 18, 35), (0, j), (_W, j))
        # draw non-box-wall platforms only (box walls are invisible!)
        for p in self.pf:
            if p not in self._bw:
                pygame.draw.rect(s, c2, p)
                pygame.draw.rect(s, c3, p, 2)
        # draw exit
        self.xb._v(s)

    def _n(self, s, p):
        _ht(s, self._NM, _W // 2, _H - 28, c1, ctr=True)
        # mysterious "???" hint
        _ht(s,
             "".join(chr(c) for c in (63, 63, 63)),  # "???"
             _W // 2, _H // 2 - 20, c2, ctr=True, sz=48)


# ===========================================================================
# _run  --  Main game loop
# ===========================================================================
def _run():
    pygame.init()
    pygame.display.set_caption(_LBL_G)
    s  = pygame.display.set_mode((_W, _H))
    cl = pygame.time.Clock()

    # validate environment
    if not _validate_env():
        sys.exit(1)

    # title screen
    _scr_t(s, cl)

    # create player
    p = _Eq(60, 400)

    # stage class list
    _lv = [_S1, _S2, _S3, _S4, _S5, _S6]
    idx = 0

    def _mk(i):
        """Make level i: resets player state and instantiates stage."""
        p.vx = 0
        p.vy = 0
        p.gv = _GN
        p.sp = 5
        p.bl.clear()
        return _lv[i](p)

    lv = _mk(0)

    # main loop
    while True:
        cl.tick(_F)
        ev = pygame.event.get()
        for e in ev:
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()

        # update
        lv._u(p, ev)
        # draw
        lv._v(s)
        p._v(s)
        for b in p.bl:
            b._v(s)
        lv._n(s, p)
        # stage indicator
        _ht(s, f"[{idx+1}/6]", _W - 70, _H - 26, c2, sz=16)
        pygame.display.flip()

        # stage complete?
        if lv.cp:
            idx += 1
            if idx >= len(_lv):
                _scr_w(s, cl)
                break
            else:
                _scr_r(s, cl, _lv[idx]._NM)
                lv = _mk(idx)

    pygame.quit()


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == "__main__":
    _run()


# ============================================================================
# ===================== BUG SUMMARY PER STAGE ================================
# ============================================================================
#
# STAGE 1 (_S1) -- "Collect & Exit"
#   BUG: _Ox._c() checks p.cn >= 9999 to open the door. Only 3 collectibles
#   exist in the stage (the _Rx coins). The player can never accumulate 9999
#   coins, so the door stays LOCKED forever. The stage is unbeatable.
#   FIX: Change the threshold in _Ox._c from 9999 to 3 (the actual number
#   of collectibles).
#
# STAGE 2 (_S2) -- "Timed Obstacle Course"
#   BUG: _SP = 2 -- the class attribute overrides the player's speed to 2
#   (the normal speed is 5). With the 5-second timer and the extremely slow
#   movement speed of 2, it's physically impossible to traverse the entire
#   obstacle course (905 pixels) in time. The player moves at 2 px/frame
#   = 120 px/sec, needing ~7.5 seconds for ~900 pixels, but the timer is
#   only 5 seconds.
#   FIX: Change _SP from 2 to 5 (or increase the timer).
#
# STAGE 3 (_S3) -- "Pit / Void Stage"
#   BUG: The _SCY ceiling check (p.r.top <= self._SCY where _SCY = _H - 239
#   = 361) resets the player whenever they jump high enough. The exit is at
#   _H - _T*5 = 400, but the elevated platform is at _H - _T*4 = 440.
#   Actually the ceiling at 361 blocks reaching the exit platform above.
#   The _rdb() method (rebuild bridge) exists but is NEVER CALLED, so the
#   gap across the pit has no bridge -- the player cannot cross.
#   FIX: Call self._rdb() in __init__ to build the bridge, and remove or
#   raise the _SCY ceiling check.
#
# STAGE 4 (_S4) -- "Boss Fight"
#   BUG: _Gx._td() (take damage) does: self.hp -= n; self.hp = self.mh.
#   After subtracting damage, it immediately resets hp back to max health
#   (mh = 10). The boss can NEVER die (self.hp never reaches 0), and the
#   exit only becomes accessible when self.bx.dd is True (boss dead).
#   FIX: Remove the line "self.hp = self.mh" from _Gx._td().
#
# STAGE 5 (_S5) -- "Inverted Gravity"
#   BUG 1: p.gv = _GI sets gravity to -0.5 (player floats upward).
#   BUG 2: _mj() is used instead of _mi(). In _mj, K_LEFT sets vx = +sp
#   (moves right) and K_RIGHT sets vx = -sp (moves left). Controls are
#   REVERSED compared to what the player expects.
#   BUG 3: The exit is the _Ux moving hazard, which teleports to a random
#   location whenever the player gets within 50 pixels. Combined with
#   inverted gravity and reversed controls, catching it is extremely hard.
#   FIX: Use _mi() instead of _mj(), set gravity to _GN, and either
#   remove the _Ux teleport behavior or use a static _Tx exit.
#
# STAGE 6 (_S6) -- "Invisible Wall Maze"
#   BUG: The exit _Tx at (460, 255) is placed INSIDE an invisible walled
#   box (x: 330-630, y: 140-410). The four box walls are added to self.pf
#   (collision list) but are NOT drawn in _v() (they are skipped with
#   "if p not in self._bw"). The box has NO openings/gaps, making it
#   physically impossible for the player to reach the exit inside.
#   FIX: Add an opening in one of the box walls (e.g., make the bottom
#   wall shorter to leave a gap), or move the exit outside the box.
#
# ============================================================================
