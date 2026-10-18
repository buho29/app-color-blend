from color_blend import storage


def test_read_missing_returns_none(tmp_path):
    assert storage.read(tmp_path / 'nada.json') is None


def test_write_and_read(tmp_path):
    path = tmp_path / 'sub' / 'data.json'
    storage.write(path, '{"á": 1}')
    assert storage.read(path) == '{"á": 1}'
    storage.write(path, '[]')
    assert storage.read(path) == '[]'
    assert [p.name for p in path.parent.iterdir()] == ['data.json']


def test_backup(tmp_path):
    path = tmp_path / 'data.json'
    path.write_text('roto')
    storage.backup(path)
    assert not path.exists()
    assert (tmp_path / 'data.json.bak').read_text() == 'roto'
