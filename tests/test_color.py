import pytest

from color_blend.color import Color, delta_e, rgb_to_lab, describe_delta_e


def test_hex_rgb_round_trip():
    c = Color(hex_=0x29397b)
    assert c.rgb == (0x29, 0x39, 0x7b)
    assert Color(rgb=c.rgb).hex_ == 0x29397b
    assert c.get_hex() == '#29397b'


def test_rgb_from_json_list_becomes_tuple():
    c = Color(rgb=[1, 2, 3], hex_=0x010203)
    assert c.rgb == (1, 2, 3)


def test_default_is_black():
    assert Color().rgb == (0, 0, 0)


@pytest.mark.parametrize('rgb, lab', [
    ((255, 255, 255), (100.0, 0.0, 0.0)),
    ((0, 0, 0), (0.0, 0.0, 0.0)),
    ((255, 0, 0), (53.24, 80.09, 67.20)),
])
def test_rgb_to_lab(rgb, lab):
    assert rgb_to_lab(rgb) == pytest.approx(lab, abs=0.05)


# pares de referencia de Sharma, Wu y Dalal (2005)
@pytest.mark.parametrize('lab1, lab2, expected', [
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((50.0, 2.5, 0.0), (61.0, -5.0, 29.0), 22.8977),
    ((50.0, 2.5, 0.0), (56.0, -27.0, -3.0), 31.9030),
    ((50.0, 2.5, 0.0), (58.0, 24.0, 15.0), 19.4535),
])
def test_delta_e_ciede2000(lab1, lab2, expected):
    assert delta_e(lab1, lab2) == pytest.approx(expected, abs=1e-4)
    assert delta_e(lab2, lab1) == pytest.approx(expected, abs=1e-4)


def test_delta_e_same_color_is_zero():
    lab = rgb_to_lab((12, 200, 99))
    assert delta_e(lab, lab) == 0


def test_describe_delta_e():
    assert describe_delta_e(0.5) == 'imperceptible'
    assert describe_delta_e(60) == 'distinto'
