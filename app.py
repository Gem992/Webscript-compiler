"""Flask server: serves the web UI and exposes the compiler as a JSON API."""
import os

from flask import Flask, jsonify, request, send_from_directory

from webscript import compile_source

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="/static")


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/examples")
def examples():
    folder = os.path.join(BASE, "examples")
    out = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".ws"):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                label = name[:-3].lstrip("0123456789_").replace("_", " ")
                out.append({"name": label, "source": f.read()})
    return jsonify(out)


@app.post("/api/compile")
def api_compile():
    data = request.get_json(silent=True) or {}
    source = data.get("source", "")
    if not isinstance(source, str) or len(source) > 20000:
        return jsonify({"error": "source must be a string of at most 20000 characters"}), 400
    try:
        return jsonify(compile_source(source, optimize=bool(data.get("optimize", True))))
    except Exception as exc:                      # a bug in the compiler, not in the user's program
        return jsonify({"error": f"Internal compiler error: {exc}"}), 500


if __name__ == "__main__":
    # HOST=0.0.0.0 makes the app reachable from your host machine (not only inside the VM)
    app.run(host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", "5000")),
            debug=os.environ.get("DEBUG") == "1")
