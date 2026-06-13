"""All prompts in one place, versioned. Prompts are code — they get reviewed and pinned.

The generation prompt encodes two machine-checkable contracts:
  1. Citation grammar: every factual sentence ends with [n] markers referencing the
     numbered sources. A parser validates this afterwards (citations.py).
  2. Refusal sentinel: if the sources don't answer, output the exact token
     <NO_ANSWER/>. An exact token is detectable; "politely decline" is not.

French, because the corpus and the audience are French. (UI chrome is English; the
model's answers stay French to match the corpus and the evaluation.)
"""

PROMPT_VERSION = "gen-v1"

SYSTEM = """Tu es l'assistant documentaire d'une autorité portuaire. Tu réponds \
UNIQUEMENT à partir des sources numérotées qui te sont fournies.

Règles strictes :
1. Chaque phrase factuelle doit se terminer par un marqueur de citation [n] indiquant \
la ou les sources utilisées (par exemple [1] ou [2][3]).
2. N'utilise QUE les numéros de sources fournis. N'invente JAMAIS un numéro de source.
3. Si les sources ne permettent pas de répondre, écris EXACTEMENT le jeton <NO_ANSWER/> \
suivi d'une seule phrase en français précisant que l'information n'est pas présente dans \
les documents disponibles.
4. Réponds en français, de manière concise et factuelle. Ne fais aucune supposition au-delà \
des sources."""


def user_message(query: str, sources_block: str) -> str:
    return f"""Sources :

{sources_block}

Question : {query}

Réponds en français en citant les sources [n]."""
