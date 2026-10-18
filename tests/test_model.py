import threading
from itertools import product
from math import comb, gcd

import pytest

from color_blend.color import Color, color_distance
from color_blend.mixing import MIX_PIGMENT, MIX_RGB
from color_blend.model import Model
from color_blend.palettes import VALLEJO_GAME_COLOR


@pytest.fixture
def model():
    m = Model(mix_mode=MIX_RGB)
    m.set_data(VALLEJO_GAME_COLOR)
    return m


def by_name(model, name):
    return next(c for c in model.colors if c.name == name)


def recipe(blend):
    return {(item['color'].name, item['amount']) for item in blend['colors']}


def test_finds_both_amount_orders(model):
    white, black = by_name(model, 'White'), by_name(model, 'Black')
    model.colors = [white, black]
    # 2 blancos + 1 negro y 1 blanco + 2 negros tienen que aparecer
    light = Color(rgb=(170, 170, 170))
    dark = Color(rgb=(86, 86, 86))
    for target, expected in ((light, {('White', 2), ('Black', 1)}),
                             (dark, {('White', 1), ('Black', 2)})):
        result = model.find_blend(target, max_delta_e=1, color_max=2, cant_max=2)
        assert recipe(result[0]) == expected


def test_no_duplicate_colors_and_simplest_recipe(model):
    target = Color(rgb=(128, 128, 128))
    result = model.find_blend(target, max_delta_e=100, color_max=3, cant_max=4)
    hexes = [r['new'].hex_ for r in result]
    assert len(hexes) == len(set(hexes))
    # 1:1 y no 2:2, 3:3...
    grey = next(r for r in result if r['new'].rgb == (128, 128, 128))
    assert sum(item['amount'] for item in grey['colors']) == 2


def test_results_sorted_and_within_limit(model):
    target = Color(rgb=(255, 192, 203))
    result = model.find_blend(target, max_delta_e=15, color_max=3, cant_max=3)
    assert result
    distances = [r['delta_e'] for r in result]
    assert distances == sorted(distances)
    assert all(d <= 15 for d in distances)
    for r in result:
        assert r['delta_e'] == pytest.approx(color_distance(r['new'], target))
        assert model.blend_colors(r['colors']).rgb == r['new'].rgb


def test_pigment_search_matches_blend(model):
    model.set_mix_mode(MIX_PIGMENT)
    target = Color(rgb=(90, 110, 50))
    result = model.find_blend(target, max_delta_e=20, color_max=2, cant_max=3)
    assert result
    for r in result[:20]:
        assert model.blend_colors(r['colors']).rgb == r['new'].rgb


def test_cancel_returns_none(model):
    cancel = threading.Event()
    cancel.set()
    assert model.find_blend(Color(), color_max=4, cant_max=4, cancel=cancel) is None


def test_count_combinations_matches_search(model):
    calls = []
    model.find_blend(Color(), max_delta_e=0, color_max=3, cant_max=4,
                     progress=lambda done, total: calls.append((done, total)))
    done, total = calls[-1]
    assert done == total == Model.count_combinations(13, 3, 4)


@pytest.mark.parametrize('n, color_max, cant_max', [
    (13, 4, 4), (13, 5, 10), (5, 3, 6), (3, 5, 2), (1, 1, 1),
])
def test_count_combinations_brute_force(n, color_max, cant_max):
    def coprime(k):
        return sum(1 for a in product(range(1, cant_max + 1), repeat=k) if gcd(*a) == 1)

    expected = sum(comb(n, k) * coprime(k) for k in range(1, min(n, color_max) + 1))
    assert Model.count_combinations(n, color_max, cant_max) == expected


def test_favorites_json_round_trip(model):
    blends = [{'color': by_name(model, 'White'), 'amount': 2},
              {'color': by_name(model, 'Bloody Red'), 'amount': 1}]
    model.add_favorite(blends)
    text = model.get_json_favorite()

    other = Model(mix_mode=MIX_RGB)
    events = []
    other.add_event(events.append)
    other.set_json_favorite(text)
    assert events == [Model.evt_fav_loaded]
    assert other.favorite[0]['new'].rgb == model.favorite[0]['new'].rgb
    assert recipe(other.favorite[0]) == {('White', 2), ('Bloody Red', 1)}


def test_mix_mode_change_updates_favorites(model):
    blends = [{'color': by_name(model, 'Ultra Marine Blue'), 'amount': 1},
              {'color': by_name(model, 'Sunblast Yellow'), 'amount': 1}]
    model.add_favorite(blends)
    rgb_before = model.favorite[0]['new'].rgb
    model.set_mix_mode(MIX_PIGMENT)
    assert model.favorite[0]['new'].rgb != rgb_before


def test_state_round_trip(model):
    model.add_favorite([{'color': model.colors[0], 'amount': 1}])
    model.set_mix_mode(MIX_PIGMENT)
    other = Model(mix_mode=MIX_RGB)
    other.set_json_state(model.get_json_state())
    assert other.mix_mode == MIX_PIGMENT
    assert [c.hex_ for c in other.colors] == [c.hex_ for c in model.colors]
    assert len(other.favorite) == 1


@pytest.mark.parametrize('text', [
    'hola',
    '{"a": 1}',
    '[{"rgb": [1, 2, 3], "otro": 1}]',
    '[{"rgb": [1, 2, 300]}]',
    '[1, 2]',
])
def test_invalid_colors_json(model, text):
    before = list(model.colors)
    with pytest.raises(ValueError):
        model.set_json_colors(text)
    assert model.colors == before


@pytest.mark.parametrize('text', [
    '[{"colors": []}]',
    '[{"colors": [{"amount": 0, "color": {"rgb": [1, 2, 3]}}]}]',
    '[{"new": {"rgb": [1, 2, 3]}}]',
])
def test_invalid_favorites_json(model, text):
    with pytest.raises(ValueError):
        model.set_json_favorite(text)
