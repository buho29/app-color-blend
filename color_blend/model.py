import dataclasses
import json
import logging
import math
from itertools import combinations, product

from .color import Color, delta_e, rgb_to_lab
from .mixing import MIX_PIGMENT, MIXERS, pigment_params, mix_pigment_params

logger = logging.getLogger(__name__)

STATE_VERSION = 1


class Observer:

    def __init__(self):
        self._listeners = list()

    def add_event(self, listener):
        self._listeners.append(listener)

    def dispatch_event(self, event_name: str = None):
        for listener in self._listeners:
            listener(event_name)


class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


class Model(Observer):
    evt_fav_added = 'add_favorite'
    evt_fav_removed = 'remove_favorite'
    evt_fav_loaded = 'loaded_favorite'

    evt_colors_loaded = 'loaded_colors'
    evt_mix_mode_changed = 'mix_mode_changed'

    def __init__(self, mix_mode=MIX_PIGMENT):
        super().__init__()
        self.colors = list()
        self.favorite = list()
        self.mix_mode = mix_mode

    def set_data(self, colors):
        for item in colors:
            self.colors.append(
                Color(name=item['name'], id=item['id'], hex_=item['value'])
            )

    # mezcla con el modo activo
    def blend_colors(self, colors):
        return MIXERS[self.mix_mode](colors)

    def set_mix_mode(self, mix_mode):
        if mix_mode not in MIXERS:
            raise ValueError(f'modo de mezcla desconocido: {mix_mode}')
        if mix_mode == self.mix_mode:
            return
        self.mix_mode = mix_mode
        self._update_favorites()
        self.dispatch_event(Model.evt_mix_mode_changed)

    def add_favorite(self, blends, dispatch=True):
        logger.info('add favorite %d', len(blends))
        self.favorite.append({
            'colors': blends,
            'new': self.blend_colors(blends)
        })
        if dispatch:
            self.dispatch_event(Model.evt_fav_added)

    def remove_favorite(self, index, dispatch=True):
        logger.info('remove favorite %d', index)
        del self.favorite[index]
        if dispatch:
            self.dispatch_event(Model.evt_fav_removed)

    def clear_favorites(self):
        self.favorite.clear()
        self.dispatch_event(Model.evt_fav_removed)

    def _update_favorites(self):
        # el color resultante depende del modo de mezcla
        for fav in self.favorite:
            fav['new'] = self.blend_colors(fav['colors'])

    #
    #         JSON

    def get_json_favorite(self):
        return Model.encoder_json(self.favorite)

    def get_json_colors(self):
        return Model.encoder_json(self.colors)

    def set_json_favorite(self, str_json):
        favorite = Model.decoder_json(str_json)
        _check_favorites(favorite)
        self.favorite = favorite
        self._update_favorites()
        self.dispatch_event(Model.evt_fav_loaded)

    def set_json_colors(self, str_json):
        colors = Model.decoder_json(str_json)
        _check_colors(colors)
        self.colors = colors
        self.dispatch_event(Model.evt_colors_loaded)

    def get_json_state(self):
        return Model.encoder_json({
            'version': STATE_VERSION,
            'colors': self.colors,
            'favorites': self.favorite,
            'settings': {'mix_mode': self.mix_mode},
        })

    def set_json_state(self, str_json):
        data = Model.decoder_json(str_json)
        if not isinstance(data, dict):
            raise ValueError('estado no válido')
        colors = data.get('colors', [])
        favorite = data.get('favorites', [])
        _check_colors(colors)
        _check_favorites(favorite)
        mix_mode = data.get('settings', {}).get('mix_mode', self.mix_mode)
        if mix_mode not in MIXERS:
            mix_mode = self.mix_mode

        self.colors = colors
        self.favorite = favorite
        self.mix_mode = mix_mode
        self._update_favorites()
        self.dispatch_event(Model.evt_colors_loaded)
        self.dispatch_event(Model.evt_fav_loaded)

    #
    #         Búsqueda

    # busca las mejores mezclas (blends) para un color determinado
    # devuelve las mezclas con un ΔE <= max_delta_e ordenadas de mejor a peor
    # devuelve None si se cancela
    def find_blend(
            self, color_target,
            max_delta_e=10.0, color_max=4, cant_max=4,
            cancel=None, progress=None):
        search = self.iter_find_blend(color_target, max_delta_e, color_max, cant_max)
        try:
            while True:
                done, total = next(search)
                if cancel is not None and cancel.is_set():
                    search.close()
                    return None
                if progress is not None:
                    progress(done, total)
        except StopIteration as e:
            return e.value

    # igual que find_blend pero por pasos: es un generador que produce
    # (mezclas probadas, total) cada `step` mezclas y devuelve el resultado
    # al terminar (StopIteration.value). Así la UI puede buscar sin hilos.
    def iter_find_blend(
            self, color_target,
            max_delta_e=10.0, color_max=4, cant_max=4, step=512):
        # el estado se copia ahora y no al empezar a iterar
        colors = list(self.colors)
        mix_mode = self.mix_mode
        return self._iter_find_blend(
            colors, mix_mode, color_target, max_delta_e, color_max, cant_max, step)

    @staticmethod
    def _iter_find_blend(colors, mix_mode, color_target,
                         max_delta_e, color_max, cant_max, step):
        len_colors = len(colors)
        total = Model.count_combinations(len_colors, color_max, cant_max)
        target_lab = color_target.get_lab()

        if mix_mode == MIX_PIGMENT:
            params = [pigment_params(c) for c in colors]

            def mix(comb, amounts):
                return mix_pigment_params([params[i] for i in comb], amounts)
        else:
            def mix(comb, amounts):
                n = sum(amounts)
                return tuple(
                    round(sum(colors[i].rgb[ch] * a for i, a in zip(comb, amounts)) / n)
                    for ch in range(3)
                )

        distances = dict()  # rgb -> ΔE
        best = dict()  # rgb -> (ΔE, gotas totales, comb, amounts)
        count = 0
        for num_colors in range(1, min(color_max, len_colors) + 1):
            # cantidades de cada color en cualquier orden (1:2 y 2:1),
            # sin las proporcionales (2:2 es lo mismo que 1:1)
            amount_sets = [
                a for a in product(range(1, cant_max + 1), repeat=num_colors)
                if math.gcd(*a) == 1
            ]
            for comb in combinations(range(len_colors), num_colors):
                for amounts in amount_sets:
                    if num_colors == 1:
                        rgb = colors[comb[0]].rgb
                    else:
                        rgb = mix(comb, amounts)

                    d = distances.get(rgb)
                    if d is None:
                        d = delta_e(rgb_to_lab(rgb), target_lab)
                        distances[rgb] = d

                    if d <= max_delta_e:
                        drops = sum(amounts)
                        found = best.get(rgb)
                        # si el color ya existe nos quedamos con la receta más simple
                        if found is None or drops < found[1]:
                            best[rgb] = (d, drops, comb, amounts)

                    count += 1
                    if count % step == 0:
                        yield count, total

        yield count, total
        logger.info('iteraciones %d numero de resultados %d', count, len(best))

        result = list()
        for rgb, (d, drops, comb, amounts) in sorted(best.items(), key=lambda x: x[1][:2]):
            result.append({
                'colors': [
                    {'amount': a, 'color': colors[i]} for i, a in zip(comb, amounts)
                ],
                'delta_e': d,
                'new': Color(rgb=rgb),
            })
        return result

    #
    #         Static methods

    # número de mezclas que probará find_blend
    @staticmethod
    def count_combinations(len_colors, color_max, cant_max):
        total = 0
        for k in range(1, min(color_max, len_colors) + 1):
            total += math.comb(len_colors, k) * _count_coprime_tuples(cant_max, k)
        return total

    # json decoder
    @staticmethod
    def as_color(dct):
        if 'rgb' in dct:
            return Color(**dct)
        return dct

    # json encoder
    @staticmethod
    def encoder_json(data):
        json_string = json.dumps(
            data, cls=DataclassJSONEncoder, indent=4)
        return json_string

    @staticmethod
    def decoder_json(json_string):
        try:
            return json.loads(
                json_string,
                object_hook=Model.as_color
            )
        except (TypeError, ValueError) as e:
            raise ValueError(f'JSON no válido: {e}') from e


###################################
#            validación
###################################

def _is_valid_color(color):
    return (
        isinstance(color, Color)
        and len(color.rgb) == 3
        and all(isinstance(v, int) and 0 <= v <= 255 for v in color.rgb)
    )


def _check_colors(colors):
    if not isinstance(colors, list) or not all(_is_valid_color(c) for c in colors):
        raise ValueError('la lista de colores no es válida')


def _check_favorites(favorite):
    if not isinstance(favorite, list):
        raise ValueError('la lista de favoritos no es válida')
    for fav in favorite:
        items = fav.get('colors') if isinstance(fav, dict) else None
        if not isinstance(items, list) or not items:
            raise ValueError('un favorito no tiene colores')
        for item in items:
            if (not isinstance(item, dict)
                    or not _is_valid_color(item.get('color'))
                    or not isinstance(item.get('amount'), int)
                    or item['amount'] < 1):
                raise ValueError('un favorito tiene un color no válido')


# tuplas de longitud k con valores 1..m cuyo mcd es 1 (inversión de Möbius)
def _count_coprime_tuples(m, k):
    mu = [0, 1] + [0] * (m - 1)
    for d in range(1, m + 1):
        for multiple in range(2 * d, m + 1, d):
            mu[multiple] -= mu[d]
    return sum(mu[d] * (m // d) ** k for d in range(1, m + 1))
