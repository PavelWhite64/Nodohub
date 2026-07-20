from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from .models import PageConfig

TEMPLATES_DIR = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

def render_page(config: PageConfig) -> str:
    template_name = f"{config.theme}.html"
    template = env.get_template(template_name)
    # Проверка аватара
    avatar_url = None
    for ext in ["png", "jpg", "jpeg", "webp"]:
        path = Path("static/avatars") / f"{config.username}.{ext}"
        if path.exists():
            avatar_url = f"/avatars/{config.username}.{ext}"
            break
    return template.render(
        **config.model_dump(),
        avatar_url=avatar_url
    )