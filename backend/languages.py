LANGUAGES: dict[str, str] = {
    "de": "Deutsch",
    "en": "English",
}

# English names, used only when instructing the LLM — English-language
# prompts get followed more reliably than German ones, even when they
# request a reply in a different language, so the persona system prompt is
# written in English while still requiring a reply in the target Language.
# Distinct from LANGUAGES above, which is the German-facing UI display name.
LANGUAGE_NAMES_EN: dict[str, str] = {
    "de": "German",
    "en": "English",
}

DEFAULT_LANGUAGE_ID = "de"
