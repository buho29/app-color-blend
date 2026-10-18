"""Modelos de mezcla.

Cada mezcla es una lista de {'amount': gotas, 'color': Color}.
"""
import math

from .color import Color, srgb_to_linear, linear_to_srgb

MIX_PIGMENT = 'pigment'
MIX_RGB = 'rgb'

# reflectancia mínima: un pigmento real nunca absorbe el 100% de un canal,
# sin este límite un amarillo puro (azul = 0) dejaría a 0 el azul de cualquier mezcla
_R_MIN = 0.01


def blend_rgb(colors):
    """Media ponderada en sRGB (mezcla de luz, no de pintura)."""
    total = 0
    rt, gt, bt = 0, 0, 0
    for item in colors:
        amount = item['amount']
        r, g, b = item['color'].rgb
        rt += r * amount
        gt += g * amount
        bt += b * amount
        total += amount
    return Color(rgb=(
        round(rt / total),
        round(gt / total),
        round(bt / total)
    ))


def pigment_params(color):
    """Logaritmo de la reflectancia lineal de cada canal de un color."""
    return tuple(
        math.log(max(_R_MIN, srgb_to_linear(c / 255))) for c in color.rgb
    )


def mix_pigment_params(params, amounts):
    """Mezcla parámetros precalculados con pigment_params(); devuelve tupla sRGB."""
    total = 0
    l0 = l1 = l2 = 0.0
    for (p0, p1, p2), amount in zip(params, amounts):
        l0 += p0 * amount
        l1 += p1 * amount
        l2 += p2 * amount
        total += amount
    return tuple(
        round(linear_to_srgb(math.exp(v / total)) * 255) for v in (l0, l1, l2)
    )


def blend_pigment(colors):
    """Mezcla sustractiva aproximada.

    Media geométrica ponderada de la reflectancia de cada canal (cada pintura
    absorbe parte de la luz que deja pasar la otra). Es una aproximación: con
    solo 3 canales no se puede reproducir el espectro real de un pigmento.
    """
    if len(colors) == 1:
        return Color(rgb=colors[0]['color'].rgb)
    params = [pigment_params(item['color']) for item in colors]
    amounts = [item['amount'] for item in colors]
    return Color(rgb=mix_pigment_params(params, amounts))


MIXERS = {
    MIX_PIGMENT: blend_pigment,
    MIX_RGB: blend_rgb,
}
