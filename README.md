# app-color-blend

Find the recipe for mixing a color from a paint set (Vallejo Game Color).

Busca la receta de la mezcla de un color desde un conjunto de pinturas (Vallejo Game Color).

![Buscar](buscar.jpg)

![Mezclar](mezcla.jpg)

![Favoritos](favorito.jpg)

![Export/Import](export.jpg)

## Descarga / Download

En Windows no hace falta instalar Python: descarga [`color-blend.exe`](color-blend.exe) y ábrelo.

*On Windows, just download [`color-blend.exe`](color-blend.exe) and run it.*

## Funciones / Features

- **Buscar color**: elige un color (selector o cuentagotas de pantalla) y la app prueba todas las
  mezclas posibles de la paleta para mostrar las 8 más parecidas.
  *Pick a color (chooser or screen eyedropper) and get the 8 closest mixes from the palette.*
- **Mezclar color**: añade gotas de cada pintura y mira el resultado al momento.
  *Add drops of each paint and see the result.*
- **Favoritos**: guarda las recetas que te interesen. Se guardan solas en disco.
  *Save recipes; they are stored automatically.*
- **Export/Import**: copia o pega la paleta y los favoritos como JSON (portapapeles o archivo).
  *Copy/paste palette and favorites as JSON (clipboard or file).*

## Modos de mezcla / Mix modes

Arriba a la derecha puedes elegir cómo se calcula el color que sale al mezclar. La diferencia está
en si se imita la mezcla de **luz** o la de **pintura**.

*Top right selector: mix like light (RGB average) or like paint (subtractive).*

### Luz (RGB)

Hace la media de los valores RGB de cada color, teniendo en cuenta las gotas. Por ejemplo, 1 gota
de blanco (255) y 1 de negro (0) dan 128, un gris medio.

Así se comporta la **luz**, como dos focos de colores apuntando a la misma pared. La pintura no
funciona así: azul + amarillo da un caqui en lugar de verde, y el negro apenas tiñe.

### Pigmento (por defecto)

La pintura no emite luz, la **absorbe**. El azul absorbe casi todo el rojo y el verde, y el
amarillo absorbe casi todo el azul. Al mezclarlos, cada uno quita su parte. Lo único que ninguno
de los dos absorbe del todo es el verde, y eso es lo que ves.

Para simularlo, la app calcula qué parte de la luz devuelve cada pintura en cada canal (rojo,
verde y azul) y las **multiplica** en vez de sumarlas: cada pintura filtra la luz que deja pasar
la otra. Técnicamente es una media geométrica de la reflectancia de cada canal, ponderada por las
gotas.

| Mezcla | Luz (RGB) | Pigmento | En pintura real |
|---|---|---|---|
| azul + amarillo | `#94903e` caqui | `#6c763c` verde oliva | verde |
| rojo + amarillo | `#e6740c` | `#e55419` naranja | naranja |
| negro + blanco 1:1 | `#808080` gris medio | `#595959` gris oscuro | gris oscuro |
| rojo + blanco 1:8 | rosa | `#f9cbcb` rosa pálido | rosa pálido |
| verde + rojo | grisáceo | `#904a1d` marrón | marrón |

Ninguna pintura real absorbe el 100 % de un canal, así que la app supone que siempre devuelve al
menos un 1 % de la luz. Sin ese mínimo, un amarillo puro (con el azul a 0) dejaría a cero el azul
de cualquier mezcla, aunque se añadiera mucho blanco.

*Paint absorbs light: the app multiplies the per-channel reflectance of each paint (weighted
geometric mean), so blue + yellow gives green and red + white gives pink.*

### Limitaciones / Limitations

El modo Pigmento es **una aproximación**, no una simulación exacta:

- Un pigmento real tiene un espectro completo, y aquí solo hay 3 números por color. Dos pinturas
  que se ven iguales en pantalla pueden mezclar distinto en la realidad.
- No tiene en cuenta la **fuerza tintórea**: hay pinturas que tiñen mucho más que otras con la
  misma cantidad, pero aquí 1 gota pesa lo mismo sea la pintura que sea.
- Los colores de la paleta son aproximados, porque una pantalla no reproduce exactamente la
  pintura.

Las recetas dan un buen punto de partida, pero conviene probar la mezcla y ajustarla a ojo.

*Pigment mode is an approximation: use the recipes as a starting point and adjust by eye.*

### Al cambiar de modo / When switching modes

- Los favoritos se recalculan, porque cada uno guarda la receta (pinturas y gotas) y no el color
  final.
- Los resultados de «Buscar Color» se borran y hay que volver a buscar.
- El modo elegido se guarda para la próxima vez.

## ΔE

El parecido entre colores se mide con **CIEDE2000 (ΔE)**, que tiene en cuenta cómo percibe el ojo
las diferencias. Orientativo: < 1 imperceptible, 1–2 solo se nota de cerca, 2–10 se nota a simple
vista. En «Buscar Color», el campo «ΔE máx.» indica cuánto se puede alejar una mezcla del color
buscado para aparecer en los resultados.

*Color difference uses CIEDE2000; "ΔE máx." is the maximum difference allowed in search results.*

## Datos guardados / Saved data

La paleta, los favoritos y el modo de mezcla se guardan en:

- Windows: `%APPDATA%\ColorBlend\data.json`
- Linux / macOS / Android: `~/.color_blend/data.json`

Si el archivo se estropea, se renombra a `data.json.bak` y la app arranca con la paleta por defecto.

## Desarrollo / Development

Requiere Python 3.9 o superior con `tkinter`.

```sh
pip install -r requirements.txt
python main.py
```

### Tests

```sh
pip install -r requirements-dev.txt
pytest
```

### Crear el ejecutable / Build the executable

```sh
pyinstaller --onefile --noconsole --name color-blend main.py
```

El ejecutable se genera en `dist/color-blend.exe`. Para publicarlo, cópialo a la raíz del
repositorio sustituyendo a `color-blend.exe`.

### Estructura / Layout

| Archivo | Contenido |
|---|---|
| `main.py` | punto de entrada |
| `color_blend/color.py` | `Color`, conversión a Lab y ΔE (CIEDE2000) |
| `color_blend/mixing.py` | modos de mezcla (pigmento y RGB) |
| `color_blend/model.py` | modelo: paleta, favoritos, búsqueda de mezclas, JSON |
| `color_blend/storage.py` | guardado en disco |
| `color_blend/palettes.py` | paleta Vallejo Game Color |
| `color_blend/widgets.py` | widgets de customtkinter |
| `color_blend/views.py` | pestañas de la app |
| `color_blend/app.py` | ventana principal |
| `tests/` | tests de la lógica (pytest) |
