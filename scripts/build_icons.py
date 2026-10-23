#!/usr/bin/env python3
"""Генерирует объёмные SVG-иллюстрации в dist/assets/icons.

Стиль «coin» — серебряная монета с бирюзовым символом (крупные плитки),
стиль «glass» — полупрозрачный лавандовый символ (промо-плитки в шапке).
Чтобы заменить иллюстрацию на PNG, положите файл с тем же именем
в dist/assets/medsi/ (например, heart.png или glass-chat.png).
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "dist" / "assets" / "icons"

# Символы в поле 48×48. url(#g) — основной градиент, url(#d) — тёмный оттенок.
GLYPHS = {
    "heart": '<path fill="url(#g)" d="M24 43C10 33 3.5 25.5 3.5 16.5 3.5 9.8 8.6 5 14.8 5c4 0 7.2 2 9.2 5 2-3 5.2-5 9.2-5 6.2 0 11.3 4.8 11.3 11.5C44.5 25.5 38 33 24 43z"/>'
             '<path d="M9 22h8l3.2-6.5 5.3 12.5 3.2-6H39" fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/>',
    "clipboard": '<rect x="7" y="8" width="34" height="37" rx="7" fill="url(#g)"/>'
                 '<rect x="15.5" y="3" width="17" height="10" rx="5" fill="url(#d)"/>'
                 '<rect x="14" y="21" width="20" height="3.6" rx="1.8" fill="#fff"/>'
                 '<rect x="14" y="29" width="14" height="3.6" rx="1.8" fill="#fff" opacity=".85"/>'
                 '<rect x="14" y="37" width="9" height="3.6" rx="1.8" fill="#fff" opacity=".7"/>',
    "chart": '<rect x="5" y="27" width="10" height="17" rx="5" fill="url(#g)" opacity=".75"/>'
             '<rect x="19" y="17" width="10" height="27" rx="5" fill="url(#g)" opacity=".9"/>'
             '<rect x="33" y="5" width="10" height="39" rx="5" fill="url(#g)"/>',
    "pill": '<g transform="rotate(-45 24 24)"><path fill="url(#g)" d="M14 14.5h10v19H14a9.5 9.5 0 0 1 0-19z"/>'
            '<path fill="url(#l)" d="M24 14.5h10a9.5 9.5 0 0 1 0 19H24z"/>'
            '<path d="M11 20h8" stroke="#fff" stroke-width="2.6" stroke-linecap="round" opacity=".75"/></g>',
    "chat": '<path fill="url(#g)" d="M5 11a7 7 0 0 1 7-7h24a7 7 0 0 1 7 7v17a7 7 0 0 1-7 7H21l-9.5 8.5V35A7 7 0 0 1 5 28z"/>'
            '<circle cx="15" cy="19.5" r="3" fill="#fff"/><circle cx="24" cy="19.5" r="3" fill="#fff"/><circle cx="33" cy="19.5" r="3" fill="#fff"/>',
    "plan": '<rect x="5" y="9" width="38" height="35" rx="8" fill="url(#g)"/>'
            '<rect x="12.5" y="4" width="5" height="11" rx="2.5" fill="url(#d)"/><rect x="30.5" y="4" width="5" height="11" rx="2.5" fill="url(#d)"/>'
            '<path d="M15 28l6 6 12-12.5" fill="none" stroke="#fff" stroke-width="4.4" stroke-linecap="round" stroke-linejoin="round"/>',
    "doctor": '<path d="M9 5v13a9.5 9.5 0 0 0 19 0V5" fill="none" stroke="url(#g)" stroke-width="5" stroke-linecap="round"/>'
              '<path d="M18.5 28v4a9.5 9.5 0 0 0 19 0v-5" fill="none" stroke="url(#g)" stroke-width="5" stroke-linecap="round"/>'
              '<circle cx="37.5" cy="20" r="7" fill="url(#d)"/><circle cx="37.5" cy="20" r="2.8" fill="#fff"/>',
    "shield": '<path fill="url(#g)" d="M24 3l17.5 6.2V21c0 11-7.2 19.3-17.5 24C13.7 40.3 6.5 32 6.5 21V9.2z"/>'
              '<path d="M16 24l6 6 11-12" fill="none" stroke="#fff" stroke-width="4.4" stroke-linecap="round" stroke-linejoin="round"/>',
    "bell": '<path fill="url(#g)" d="M24 4.5c-8 0-13.5 6-13.5 13.5v7.5L6 33.5h36l-4.5-8V18C37.5 10.5 32 4.5 24 4.5z"/>'
            '<circle cx="24" cy="39.5" r="5" fill="url(#d)"/>',
    "user": '<circle cx="24" cy="15" r="10" fill="url(#g)"/>'
            '<path fill="url(#g)" d="M5.5 44c1-10.5 8.5-16 18.5-16s17.5 5.5 18.5 16z"/>',
    "phone": '<path fill="url(#g)" d="M13.5 4.5l7 9.5-4.6 4.6c2.2 5.4 5.9 9.2 11.4 11.5l4.6-4.6 9.6 6.8-3.4 8C19 41.6 5.5 28.5 6.3 9.5z"/>',
}

PALETTES = {
    "teal": ("#6fe6dc", "#10a49c", "#0b7f79", "#c9f3ef"),
    "danger": ("#ff9da3", "#e4535d", "#b9343e", "#ffd9dc"),
    "violet": ("#e4e7ff", "#9aa4f5", "#7480e6", "#f4f5ff"),
}

COIN = {name: "teal" for name in GLYPHS} | {"phone": "danger"}
GLASS = {name: "violet" for name in GLYPHS} | {"phone": "danger"}


def gradients(palette: str) -> str:
    light, main, dark, soft = PALETTES[palette]
    return (
        f'<linearGradient id="g" x1="0" y1="0" x2=".75" y2="1"><stop offset="0" stop-color="{light}"/><stop offset="1" stop-color="{main}"/></linearGradient>'
        f'<linearGradient id="d" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{main}"/><stop offset="1" stop-color="{dark}"/></linearGradient>'
        f'<linearGradient id="l" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="{soft}"/></linearGradient>'
        '<linearGradient id="gloss" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    )


def gloss(glyph: str) -> str:
    """Блик поверх основных частей символа."""
    parts = [chunk for chunk in glyph.split("/>") if "url(#g)" in chunk]
    return "".join(chunk.replace("url(#g)", "url(#gloss)") + "/>" for chunk in parts if not chunk.startswith("<g"))


def coin(name: str) -> str:
    glyph, palette = GLYPHS[name], COIN[name]
    dark = PALETTES[palette][2]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><defs>{gradients(palette)}
<radialGradient id="face" cx=".34" cy=".28" r=".8"><stop offset="0" stop-color="#fff"/><stop offset=".45" stop-color="#f2f4f8"/><stop offset=".85" stop-color="#d6dbe4"/><stop offset="1" stop-color="#c4cad5"/></radialGradient>
<linearGradient id="rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#eef0f4"/><stop offset="1" stop-color="#a7aebb"/></linearGradient>
<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3.5"/></filter>
<filter id="lift" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="1.2" dy="2.4" stdDeviation="1.6" flood-color="{dark}" flood-opacity=".35"/></filter></defs>
<ellipse cx="63" cy="108" rx="34" ry="5.5" fill="#1f2a55" opacity=".14" filter="url(#blur)"/>
<circle cx="63.5" cy="59.5" r="44" fill="url(#rim)"/>
<circle cx="58" cy="56" r="44" fill="url(#face)"/>
<circle cx="58" cy="56" r="40.5" fill="none" stroke="#fff" stroke-opacity=".95" stroke-width="1.6"/>
<circle cx="58" cy="56" r="36.5" fill="none" stroke="#8d97a8" stroke-opacity=".16"/>
<g transform="translate(28 25) scale(1.25)" filter="url(#lift)">{glyph}{gloss(glyph)}</g></svg>
'''


def glass(name: str) -> str:
    glyph, palette = GLYPHS[name], GLASS[name]
    dark = PALETTES[palette][2]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><defs>{gradients(palette)}
<filter id="lift" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="2" dy="5" stdDeviation="4" flood-color="{dark}" flood-opacity=".35"/></filter></defs>
<g transform="translate(14 12) scale(1.9)" filter="url(#lift)" opacity=".96">{glyph}{gloss(glyph)}</g></svg>
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in GLYPHS:
        (OUT / f"{name}.svg").write_text(coin(name), encoding="utf-8")
        (OUT / f"glass-{name}.svg").write_text(glass(name), encoding="utf-8")
    print(f"Создано {len(GLYPHS) * 2} иллюстраций в {OUT}")


if __name__ == "__main__":
    main()
