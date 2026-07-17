# Nodohub

Приватный, быстрый, статический генератор персональных страниц-визиток.
Никаких трекеров, скриптов и аналитики. Только HTML + CSS.

## Философия
- Загрузка за 50 мс
- Ноль JavaScript
- Никаких внешних зависимостей
- Открытый исходный код

## Быстрый старт

### Локально
```bash
pip install -r requirements.txt
python main.py generate --config examples/anna.json
# открой static/anna.html в браузере