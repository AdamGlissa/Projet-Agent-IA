"""Agent orchestrateur pour la recherche et le résumé de papiers scientifiques.

Trois subagents spécialisés : recherche, rédaction, relecture (voir `subagents.py`).
Les subagents sont isolés (ils ne voient pas la conversation du parent) mais
partagent le système de fichiers de l'état : c'est par là qu'ils se passent le
travail.
"""

from deepagents import create_deep_agent

from subagents import SUBAGENTS
from system_prompts import load_prompt

MODEL = "anthropic:claude-opus-5"

agent = create_deep_agent(
    model=MODEL,
    system_prompt=load_prompt("orchestrator"),
    subagents=SUBAGENTS,
)
