# V0.1 tests

Run from the repository root:

    python -m pip install -r v0.1/requirements.txt
    PYTHONPATH=v0.1 python -m unittest discover -s v0.1/tests -v

The Python suite validates the JSON Schema, refuses lossy Blockbench inputs, checks supported model round-trip semantics, and verifies both vanilla and GeckoLib project generation.
