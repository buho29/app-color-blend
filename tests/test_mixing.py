from color_blend.color import Color
from color_blend.mixing import blend_pigment, blend_rgb

BLUE = Color(hex_=0x29397b)
YELLOW = Color(hex_=0xffe700)
RED = Color(hex_=0xce0018)
WHITE = Color(hex_=0xffffff)
BLACK = Color(hex_=0x010101)


def mix(*pairs):
    return [{'color': c, 'amount': a} for c, a in pairs]


def test_rgb_white_black_is_grey():
    assert blend_rgb(mix((WHITE, 1), (BLACK, 1))).rgb == (128, 128, 128)


def test_rgb_respects_amounts():
    assert blend_rgb(mix((WHITE, 3), (BLACK, 1))).rgb == (192, 192, 192)


def test_single_color_is_itself():
    for blend in (blend_rgb, blend_pigment):
        assert blend(mix((BLUE, 3))).rgb == BLUE.rgb
        assert blend(mix((BLACK, 1))).rgb == BLACK.rgb


def test_pigment_blue_yellow_is_green():
    r, g, b = blend_pigment(mix((BLUE, 1), (YELLOW, 1))).rgb
    assert g > r and g > b


def test_rgb_blue_yellow_is_not_green():
    r, g, b = blend_rgb(mix((BLUE, 1), (YELLOW, 1))).rgb
    assert r >= g


def test_pigment_red_white_is_pink():
    r, g, b = blend_pigment(mix((RED, 1), (WHITE, 8))).rgb
    assert r > 230 and 180 < g < 230 and 180 < b < 230


def test_pigment_red_yellow_is_orange():
    r, g, b = blend_pigment(mix((RED, 1), (YELLOW, 1))).rgb
    assert r > 200 and 50 < g < 150 and b < 50


def test_pigment_white_black_is_dark_grey():
    r, g, b = blend_pigment(mix((WHITE, 1), (BLACK, 1))).rgb
    assert r == g == b
    # la pintura negra tiñe mucho más que la media rgb (128)
    assert 40 < r < 110


def test_pigment_more_white_is_lighter():
    light = blend_pigment(mix((RED, 1), (WHITE, 4))).get_bright()
    dark = blend_pigment(mix((RED, 1), (WHITE, 1))).get_bright()
    assert light > dark
