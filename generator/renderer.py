from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from .models import PageConfig

TEMPLATES_DIR = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

def render_page(config: PageConfig) -> str:
    template_name = f"{config.theme}.html"
    template = env.get_template(template_name)
    return template.render(config.model_dump())

def save_page(config: PageConfig, output_dir: Path = Path("static")) -> Path:
    html = render_page(config)
    output_dir.mkdir(exist_ok=True)
    filepath = output_dir / f"{config.username}.html"
    filepath.write_text(html, encoding="utf-8")
    return filepath