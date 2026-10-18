import math
from dataclasses import dataclass
from functools import lru_cache


# Item data
@dataclass
class Color:
    rgb: tuple[int, int, int] = None
    hex_: int = None
    name: str = ''
    id: str = '-1'

    def __post_init__(self):
        if self.rgb is not None:
            # desde json llega como lista
            self.set_rgb(self.rgb)
        elif self.hex_ is not None:
            self.set_hex(self.hex_)
        else:
            self.set_hex(0)

    def set_rgb(self, rgb):
        rgb = tuple(int(v) for v in rgb[:3])
        self.hex_ = Color.get_hex_value(rgb)
        self.rgb = rgb

    def set_hex(self, hex_value):
        self.hex_ = hex_value
        self.rgb = Color.get_rgb_value(hex_value)

    def set(self, color):
        self.set_rgb(color.rgb)

    def get_hex(self):
        r, g, b = self.rgb
        return f'#{r:02x}{g:02x}{b:02x}'

    def get_bright(self):
        r, g, b = self.rgb
        return int((r + g + b) / 3)

    def get_lab(self):
        return rgb_to_lab(self.rgb)

    @staticmethod
    def get_hex_value(rgb):
        r, g, b = rgb
        return (r << 16) | (g << 8) | b

    @staticmethod
    def get_rgb_value(hex_):
        return (
            hex_ >> 16,
            (hex_ >> 8) & 0xff,
            hex_ & 0xff
        )


###################################
#      sRGB <-> lineal <-> Lab
###################################

def srgb_to_linear(c):
    """Canal sRGB (0-1) a luz lineal (0-1)."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    """Canal lineal (0-1) a sRGB (0-1)."""
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * c ** (1 / 2.4) - 0.055


# blanco de referencia D65
_XN, _YN, _ZN = 0.95047, 1.0, 1.08883
_EPS = (6 / 29) ** 3


def _lab_f(t):
    if t > _EPS:
        return t ** (1 / 3)
    return t / (3 * (6 / 29) ** 2) + 4 / 29


@lru_cache(maxsize=4096)
def rgb_to_lab(rgb):
    """Tupla sRGB (0-255) a CIELAB (D65)."""
    r, g, b = (srgb_to_linear(v / 255) for v in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / _XN
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / _YN
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / _ZN
    fx, fy, fz = _lab_f(x), _lab_f(y), _lab_f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(lab1, lab2):
    """Diferencia de color CIEDE2000 entre dos colores Lab.

    Orientativo: <1 imperceptible, 1-2 solo de cerca, 2-10 a simple vista.
    """
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    c_bar7 = ((math.hypot(a1, b1) + math.hypot(a2, b2)) / 2) ** 7
    g = 0.5 * (1 - math.sqrt(c_bar7 / (c_bar7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (a1p or b1) else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (a2p or b2) else 0.0

    dl = l2 - l1
    dc = c2p - c1p
    if c1p * c2p == 0:
        dh = 0.0
    else:
        dh = h2p - h1p
        if dh > 180:
            dh -= 360
        elif dh < -180:
            dh += 360
    dh_big = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh) / 2)

    l_bar = (l1 + l2) / 2
    c_bar_p = (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        h_bar = (h1p + h2p + 360) / 2
    else:
        h_bar = (h1p + h2p - 360) / 2

    t = (1
         - 0.17 * math.cos(math.radians(h_bar - 30))
         + 0.24 * math.cos(math.radians(2 * h_bar))
         + 0.32 * math.cos(math.radians(3 * h_bar + 6))
         - 0.20 * math.cos(math.radians(4 * h_bar - 63)))
    d_theta = 30 * math.exp(-((h_bar - 275) / 25) ** 2)
    c_bar_p7 = c_bar_p ** 7
    r_c = 2 * math.sqrt(c_bar_p7 / (c_bar_p7 + 25 ** 7))
    s_l = 1 + 0.015 * (l_bar - 50) ** 2 / math.sqrt(20 + (l_bar - 50) ** 2)
    s_c = 1 + 0.045 * c_bar_p
    s_h = 1 + 0.015 * c_bar_p * t
    r_t = -math.sin(math.radians(2 * d_theta)) * r_c

    return math.sqrt(
        (dl / s_l) ** 2 + (dc / s_c) ** 2 + (dh_big / s_h) ** 2
        + r_t * (dc / s_c) * (dh_big / s_h)
    )


def color_distance(c1, c2):
    """ΔE (CIEDE2000) entre dos Color."""
    return delta_e(c1.get_lab(), c2.get_lab())


def describe_delta_e(d):
    if d < 1:
        return 'imperceptible'
    if d < 2:
        return 'solo se nota de cerca'
    if d < 10:
        return 'se nota a simple vista'
    if d < 50:
        return 'parecido'
    return 'distinto'
