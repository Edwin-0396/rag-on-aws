import importlib.util, pathlib
src = pathlib.Path(__file__).parents[1] / "app" / "main.py"
code = src.read_text().split("@app.get")[0]
def test_chunk_overlap():
    ns = {}
    exec("def chunk" + code.split("def chunk")[1], ns)
    parts = ns["chunk"]("a" * 2000)
    assert len(parts) == 3 and all(len(p) <= 800 for p in parts)
