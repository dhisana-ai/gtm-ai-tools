from app import load_custom_parameters, UTILITY_PARAMETERS


def test_load_custom_parameters_from_python(tmp_path, monkeypatch):
    util_dir = tmp_path / 'gtm_utility'
    util_dir.mkdir()
    script = util_dir / 'demo.py'
    script.write_text(
        "import argparse\n\n"
        "def main():\n"
        "    p = argparse.ArgumentParser()\n"
        "    p.add_argument('name', help='Full name')\n"
        "    p.add_argument('--age', help='Age')\n"
    )
    monkeypatch.setattr('app.USER_UTIL_DIR', util_dir)
    UTILITY_PARAMETERS.pop('demo', None)
    load_custom_parameters()
    assert UTILITY_PARAMETERS['demo'] == [
        {'name': 'name', 'label': 'Full name'},
        {'name': '--age', 'label': 'Age'},
    ]
