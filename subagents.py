"""Les trois subagents spécialisés de l'orchestrateur.

Les `description` sont lues par l'orchestrateur pour choisir à qui déléguer :
elles disent quand utiliser le subagent, pas seulement ce qu'il est.
"""

from deepagents import SubAgent

from system_prompts import load_prompt

researcher: SubAgent = {
    "name": "researcher",
    "description": (
        "Trouve les papiers scientifiques pertinents sur un sujet et en extrait "
        "méthode, résultats chiffrés et limites. À utiliser en premier, avant toute "
        "rédaction. Écrit ses notes dans notes_recherche.md."
    ),
    "system_prompt": load_prompt("researcher"),
}

writer: SubAgent = {
    "name": "writer",
    "description": (
        "Rédige le résumé à partir des notes de recherche existantes, ou le corrige "
        "après relecture. À utiliser une fois la recherche faite. Écrit resume.md."
    ),
    "system_prompt": load_prompt("writer"),
}

reviewer: SubAgent = {
    "name": "reviewer",
    "description": (
        "Relit le résumé produit et le confronte aux notes de recherche pour "
        "vérifier sa fidélité, son exactitude et son calibrage. À utiliser après "
        "chaque rédaction. Rend son verdict dans review.md."
    ),
    "system_prompt": load_prompt("reviewer"),
}

SUBAGENTS: list[SubAgent] = [researcher, writer, reviewer]
