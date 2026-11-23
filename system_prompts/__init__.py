"""Chargement des system_prompts stockés en Markdown dans ce dossier."""

from pathlib import Path

_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Renvoie le contenu de `system_prompts/<name>.md`.

    L'encodage est forcé en UTF-8 : sous Windows la valeur par défaut est cp1252
    et les prompts contiennent des accents.
    """
    path = _DIR / f"{name}.md"
    if not path.is_file():
        available = sorted(p.stem for p in _DIR.glob("*.md"))
        raise FileNotFoundError(
            f"Prompt introuvable : {path.name}. Disponibles : {available}"
        )
    return path.read_text(encoding="utf-8")
