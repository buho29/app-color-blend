"""Guardado del estado de la app (paleta, favoritos y ajustes) en disco."""
import os
import sys
import tempfile
from pathlib import Path


def default_path():
    if sys.platform.startswith('win'):
        base = Path(os.environ.get('APPDATA') or Path.home())
        return base / 'ColorBlend' / 'data.json'
    return Path.home() / '.color_blend' / 'data.json'


def read(path):
    """Devuelve el contenido del archivo o None si no existe."""
    path = Path(path)
    if not path.exists():
        return None
    return path.read_text(encoding='utf-8')


def write(path, text):
    """Escritura atómica: nunca deja el archivo a medias."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def backup(path):
    """Renombra un archivo dañado a .bak para no sobrescribirlo."""
    path = Path(path)
    if path.exists():
        os.replace(path, path.with_suffix(path.suffix + '.bak'))
