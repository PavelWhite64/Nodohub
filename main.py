import json
import argparse
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from generator.models import PageConfig
from generator.renderer import save_page

app = FastAPI(title="Nodohub")

@app.post("/api/generate")
def generate_page(config: PageConfig):
    path = save_page(config)
    return {"url": f"/{config.username}.html"}

# Отдача статики
app.mount("/", StaticFiles(directory="static", html=True), name="static")

def cli():
    parser = argparse.ArgumentParser(description="Nodohub static page generator")
    parser.add_argument("--config", required=True, help="Path to JSON config")
    args = parser.parse_args()
    data = json.loads(Path(args.config).read_text(encoding="utf-8"))
    config = PageConfig(**data)
    path = save_page(config)
    print(f"✅ Page generated: {path}")

if __name__ == "__main__":
    import sys
    # Если первый аргумент "generate", убираем его и передаём остальное в CLI
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        sys.argv.pop(1)  # удаляем "generate"
        cli()
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)