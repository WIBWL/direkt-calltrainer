"""What the prompt frame cannot say in English, per language (ADR 0043): register
examples, patterns matched against speech, and lines spoken aloud."""

import re
from dataclasses import dataclass

# The closing veto looks back only to the nearest clause boundary: "Ich kann
# nicht länger warten, auf Wiederhören" is a goodbye; "sagen Sie nicht einfach
# tschüss" is not.
_CLAUSE_END_RE = re.compile(r"[,;.!?]")


@dataclass(frozen=True)
# pylint: disable=too-many-instance-attributes  # a configuration record
class LanguagePack:
    name_en: str
    # Register and pacing only: mid-call, nameless (the model drew names from
    # them), in a domain no Scenario uses (else reused as content).
    example_exchange: str
    # Several shapes: a single anchor gets copied verbatim into every opening.
    opening_examples: str
    # For a reverse. They name no case: a callee naming one invents the caller's reason.
    answering_examples: str
    user_closing_examples: str
    vague_reassurance_examples: str
    farewell_re: re.Pattern[str]
    postpone_re: re.Pattern[str]
    # Anchored: a greeting at the start of the Persona's reply is a restart (ADR 0038).
    regreeting_re: re.Pattern[str]
    # Exempts the turn from the repetition guards (ADR 0038).
    repeat_request_re: re.Pattern[str]
    # Same-clause words that mean the farewell is mentioned, not said. A false
    # closing cuts the call off, the expensive error.
    closing_veto_re: re.Pattern[str]
    # Vetoes an unprompted [CALL_END] when the Persona's last sentence still
    # presses (ADR 0037).
    still_pressing_re: re.Pattern[str]
    # Whisper invents these on near-silence (ADR 0071). Whole-message only:
    # "Nein, danke, das passt" is a real answer.
    stt_phantom_re: re.Pattern[str]
    # Anchored and shallow: a question word further in counts as closed.
    open_question_re: re.Pattern[str]
    # Lexical only; Whisper drops "äh".
    filler_re: re.Pattern[str]
    # The name is unknown, so `self_intro_re` matches its frame plus a capital (F-63).
    greeting_re: re.Pattern[str]
    self_intro_re: re.Pattern[str]
    # Called side offers help; the caller (a reverse) states the concern.
    offer_re: re.Pattern[str]
    concern_re: re.Pattern[str]
    # ADR 0089. `sign_off_re` is wider than `farewell_re`, which hangs up live.
    recap_re: re.Pattern[str]
    agreement_re: re.Pattern[str]
    sign_off_re: re.Pattern[str]
    fallback_closing_line: str
    # Fixed, not generated: a model round trip would only delay them (ADR 0110).
    pickup_prompts: tuple[str, ...]


# Whisper's non-speech annotations ("*Titelm*", "[Musik]") in any language.
_ANNOTATION_RE = re.compile(r"^\s*[*\[(][^*\]\)]*[*\])]\s*[.!?]*\s*$")


def is_phantom(pack: LanguagePack, user_text: str) -> bool:
    stripped = user_text.strip()
    return not stripped or bool(_ANNOTATION_RE.match(stripped)) or bool(pack.stt_phantom_re.match(stripped))


def signals_closing(pack: LanguagePack, user_text: str) -> bool:
    """A match counts only when its own clause does not veto it."""
    for pattern in (pack.farewell_re, pack.postpone_re):
        match = pattern.search(user_text)
        if match is None:
            continue
        clause = _CLAUSE_END_RE.split(user_text[: match.start()])[-1]
        if not pack.closing_veto_re.search(clause):
            return True
    return False


_GERMAN = LanguagePack(
    name_en="German",
    example_exchange=(
        "Two examples of the register, sentence length and pacing to aim for. "
        "They say nothing about how a call should unfold, only how it should "
        "sound, and they pick up mid-call: how to open one is not their "
        "subject. They are deliberately about matters that have nothing to do "
        "with yours, and they name nobody -- the only name in your call is "
        "your own, and their dates and figures are not yours either. Invent "
        "your own content, fitting YOUR scenario and character. The dialogues "
        "are in the language you must speak:\n"
        '[Caller] "Die Lieferung sollte letzten Donnerstag kommen, da ist '
        'aber nichts angekommen."\n'
        '[Other person] "Das sehe ich mir an. Haben Sie eine Auftragsnummer?"\n'
        '[Caller] "Die 4-7-2-9-1. Zugesagt war telefonisch der 14."\n'
        '[Other person] "Ich sehe hier einen neuen Termin, den 29."\n'
        '[Caller] "Das sind zwei Wochen später. Bekomme ich das schriftlich?"\n'
        "\n"
        '[Caller] "Ist im Kurs am Mittwoch noch ein Platz frei?"\n'
        '[Other person] "Welcher Starttermin denn?"\n'
        '[Caller] "Der Achtwochenkurs ab dem 6. Oktober."\n'
        '[Other person] "Da sind noch zwei Plätze frei."\n'
        '[Caller] "Gut. Bis wann muss ich mich entscheiden?"'
    ),
    opening_examples=(
        "Guten Tag, Beck mein Name, ich rufe an wegen unserer letzten Rechnung.\n"
        "Ja, guten Tag — hier ist Markus Lehmann von der Ostwald GmbH. Ich "
        "hätte eine Frage zu unserem Vertrag.\n"
        "Schönen guten Tag, Petra Winkler. Es geht um das Angebot von letzter "
        "Woche.\n"
        "Hallo, Sebastian Reuter hier. Ich wollte nochmal wegen der Lieferung "
        "nachhaken."
    ),
    answering_examples=(
        "Guten Tag, Sie sprechen mit Beck, was kann ich für Sie tun?\n"
        "Kundenservice, Lehmann am Apparat — guten Tag.\n"
        "Winkler, schönen guten Tag. Wie kann ich Ihnen helfen?\n"
        "Ja, guten Tag, hier ist Reuter. Was liegt an?"
    ),
    user_closing_examples='"das reicht mir"/"das wär\'s"',
    vague_reassurance_examples='"ich kümmere mich darum", "ich stelle das klar"',
    farewell_re=re.compile(
        r"\b(tschüss|auf wiederhören|auf wiedersehen|wiederhören|ciao)\b", re.IGNORECASE
    ),
    postpone_re=re.compile(
        r"(ein andere[rs]? mal|andermal|anders (fortsetzen|weiterführen|weitermachen)|"
        r"später (nochmal|weiter|zurückrufen)|melde mich (nochmal|später|wieder)|"
        # Not "keine Zeit mehr für X": that is a complaint, common in complaint Scenarios.
        r"rufe? (sie |dich )?(nochmal|später|zurück)|keine zeit (mehr|gerade)\b(?!\s*f(ü|ue)r)|"
        r"muss (jetzt |gleich )?(auflegen|los|schluss machen)|gespräch (beenden|abbrechen)|"
        # The look-ahead keeps "ich beende das Gespräch nicht" out; the veto
        # only reads the clause before a match.
        r"beende\w*(?:\s+\w+){0,3}\s+(gespräch|telefonat)(?!\s+(noch\s+)?nicht\b)|"
        r"lege?\s+(jetzt\s+|dann\s+|gleich\s+)?auf\b)",
        re.IGNORECASE,
    ),
    regreeting_re=re.compile(
        r"^[\s\"'>-]*(guten (tag|morgen|abend)|hallo|hi\b|servus|moin|"
        r"grüß (gott|dich)|sch(ö|oe)nen guten tag)",
        re.IGNORECASE,
    ),
    repeat_request_re=re.compile(
        r"(wie bitte\b|wer sind sie|wer war das\b|wer spricht|"
        r"wie (war|ist) (ihr|der) name|(ihren|den) namen\b.*(nochmal|noch mal|wiederhol)|"
        r"(nochmal|noch mal|noch einmal)\b.*(sagen|wiederhol|langsam)|"
        r"(sag|sagen sie( mir)?|sprechen sie)\b.*(nochmal|noch mal|noch einmal|langsamer)|"
        r"wiederholen sie|können sie das (bitte )?(nochmal |noch mal )?wiederhol|"
        # Not before a reason clause: "ich kann nicht verstehen, warum" is an objection.
        r"nicht (ganz |richtig |gut |so )?(verstanden|verstehen|mitbekommen|gehört|mitgekriegt)"
        r"\b(?!\s*,?\s*(warum|wieso|weshalb|dass))|"
        r"schlecht (zu )?(verstehen|verstanden|hören))",
        re.IGNORECASE,
    ),
    closing_veto_re=re.compile(
        r"\b(nicht|kein\w*|nie|niemals|bevor|ehe)\b", re.IGNORECASE
    ),
    still_pressing_re=re.compile(
        r"\b(ich (will|möchte|muss|brauche|erwarte)\b|wann (wird|ist|kommt|funktioniert|bekomme)\b|"
        r"ich warte (auf|noch)\b)",
        re.IGNORECASE,
    ),
    stt_phantom_re=re.compile(
        r"^\W*(vielen dank( fürs zuschauen)?|amen|untertitel\w*( (des|der|von) [\w\s,.-]+)?|"
        r"copyright [\w\s,.-]+)\W*$",
        re.IGNORECASE,
    ),
    # Longest alternatives first, so "womit" is not shadowed by "wo".
    open_question_re=re.compile(
        r"^(?:(?:und|aber|also|okay|gut|ja|nun|jetzt)[\s,]+){0,2}"
        r"(wieso|weshalb|warum|wofür|womit|worauf|worum|wohin|woher|welche[rnsm]?|"
        r"wessen|wer|wen|wem|was|wann|wo|wie)\b",
        re.IGNORECASE,
    ),
    # Word-bounded, so "halt" does not match "Haltung" or "enthalten".
    filler_re=re.compile(
        r"\b(quasi|sozusagen|gewissermaßen|irgendwie|eigentlich|halt|im\s+prinzip|"
        r"sag\s+ich\s+mal|sagen\s+wir\s+mal|ehrlich\s+gesagt)\b",
        re.IGNORECASE,
    ),
    greeting_re=re.compile(
        r"\b(guten\s+(tag|morgen|abend)|hallo|grüß\s+gott|moin|servus|herzlich\s+willkommen)\b",
        re.IGNORECASE,
    ),
    # "hier ist Schmidt", not "hier ist alles". "hier ist die Rechnung" also
    # counts, harmless for a first utterance. A bare "Schmidt, guten Tag" goes
    # unrecognised (ADR 0086).
    self_intro_re=re.compile(
        r"\bmein\s+name(?:\s+ist|:)\s+(?:(?:die|der|frau|herrn?)\s+)?(?-i:[A-ZÄÖÜ])"
        r"|\bsie\s+sprechen\s+mit\s+(?:(?:die|der|frau|herrn?)\s+)?(?-i:[A-ZÄÖÜ])"
        r"|\bhier\s+(?:ist\s+|spricht\s+)?(?!ihr\b|ihre\b|sie\b)"
        r"(?:(?:die|der|frau|herrn?)\s+)?(?-i:[A-ZÄÖÜ])"
        r"|\b(?-i:[A-ZÄÖÜ])\w+\s+am\s+apparat\b",
        re.IGNORECASE,
    ),
    offer_re=re.compile(
        r"\b((was|wie)\s+(kann|darf)\s+ich\s+(für\s+sie|ihnen)\s+(tun|helfen|weiterhelfen)"
        r"|wie\s+kann\s+ich\s+(ihnen\s+)?(helfen|weiterhelfen)"
        r"|womit\s+kann\s+ich\s+(ihnen\s+)?(helfen|dienen)|worum\s+geht\s+es"
        r"|was\s+führt\s+sie\s+zu\s+(mir|uns)|(was\s+ist\s+)?ihr\s+anliegen)",
        re.IGNORECASE,
    ),
    concern_re=re.compile(
        r"\b(ich\s+rufe\s+(sie\s+)?an\s*,?\s*(wegen|weil|bezüglich)|es\s+geht\s+um"
        r"|ich\s+melde\s+mich\s+wegen|(grund|anlass)\s+meines\s+anrufs)",
        re.IGNORECASE,
    ),
    recap_re=re.compile(
        r"\b(zusammen(gefasst|fassend)|zusammenzufassen|fasse\s+(\w+\s+){0,4}zusammen"
        r"|halten\s+wir\s+(\w+\s+){0,2}fest"
        r"|(wir\s+haben|haben\s+wir)\s+(\w+\s+){0,3}(vereinbart|besprochen|festgehalten|abgemacht)"
        r"|(ich\s+)?wiederhole\s+(\w+\s+){0,2}(kurz|noch\s*(ein)?mal))",
        re.IGNORECASE,
    ),
    # Something concrete: an action, what the other side gets, or a deadline
    # (a time noun is required). Never "ich kümmere mich darum".
    agreement_re=re.compile(
        r"\b(ich\s+(schicke|sende|maile|leite|buche|trage|reserviere|bestätige)\w*\b"
        r"|ich\s+(melde|rufe)\s+(\w+\s+){0,3}(zurück|an|bei\s+ihnen|bis)"
        r"|sie\s+(bekommen|erhalten|hören)\s+(\w+\s+){0,3}(von\s+mir|bis|morgen|heute)"
        r"|(nächste[nr]?|weitere[nr]?)\s+schritt|(so\s+)?verbleiben\s+wir|wir\s+verbleiben"
        # "so" required: "wie machen wir das?" is a question.
        r"|so\s+machen\s+wir\s+(es|das)|machen\s+wir\s+(es|das)\s+so|abgemacht"
        r"|bis\s+(spätestens\s+)?(montag|dienstag|mittwoch|donnerstag|freitag|morgen|übermorgen"
        r"|ende\s+der\s+woche|nächste[nr]?\s+woche|zum\s+\d|\d)"
        r"|(innerhalb|in)\s+(von\s+|der\s+|den\s+)?(\w+\s+){0,3}"
        r"(minute|minuten|stunde|stunden|tag|tagen|woche|wochen|monat|monaten)\b"
        r"|bis\s+zu[rm]?\s+(\w+\s+){0,3}(datum|termin|zeitpunkt|uhrzeit|frist))",
        re.IGNORECASE,
    ),
    sign_off_re=re.compile(
        r"\b(tschüss|auf\s+wiederhören|auf\s+wiedersehen|wiederhören|ciao"
        r"|schönen\s+(tag|abend|nachmittag|feierabend)|schönes\s+wochenende"
        r"|danke\s+(\w+\s+){0,2}für\s+(ihren\s+anruf|das\s+gespräch|ihre\s+zeit|ihre\s+geduld))",
        re.IGNORECASE,
    ),
    fallback_closing_line="Vielen Dank für Ihre Zeit. Auf Wiederhören.",
    pickup_prompts=("Hallo?", "Hallo? Hören Sie mich?"),
)


_ENGLISH = LanguagePack(
    name_en="English",
    example_exchange=(
        "Two examples of the register, sentence length and pacing to aim for. "
        "They say nothing about how a call should unfold, only how it should "
        "sound, and they pick up mid-call: how to open one is not their "
        "subject. They are deliberately about matters that have nothing to do "
        "with yours, and they name nobody -- the only name in your call is "
        "your own, and their dates and figures are not yours either. Invent "
        "your own content, fitting YOUR scenario and character. The dialogues "
        "are in the language you must speak:\n"
        '[Caller] "The delivery was meant to arrive last Thursday and '
        'nothing turned up."\n'
        '[Other person] "Let me check. Do you have an order number?"\n'
        '[Caller] "It is 4-7-2-9-1. I was given the 14th over the phone."\n'
        '[Other person] "I have a new date here, the 29th."\n'
        '[Caller] "That is two weeks later. Can I have that in writing?"\n'
        "\n"
        '[Caller] "Is there still a place on the Wednesday course?"\n'
        '[Other person] "Which start date do you mean?"\n'
        '[Caller] "The eight-week one, from 6 October."\n'
        '[Other person] "There are two places left."\n'
        '[Caller] "Good. When do I need to decide by?"'
    ),
    opening_examples=(
        "Hello, my name's Claire Hughes — I'm ringing about last month's "
        "invoice.\n"
        "Good afternoon, Daniel Okafor here from Ridgeway. I've got a question "
        "about our contract.\n"
        "Morning — Nina Alvarez speaking. It's about the quote you sent over "
        "last week.\n"
        "Hi, Peter Ross calling. I wanted to follow up on the delivery we "
        "discussed."
    ),
    answering_examples=(
        "Good morning, Claire Hughes speaking — how can I help?\n"
        "Customer service, Daniel here. What can I do for you?\n"
        "Hello, Nina Alvarez speaking.\n"
        "Good afternoon, Ross speaking — how can I help you today?"
    ),
    user_closing_examples='"that\'s all I needed"/"that\'ll do"',
    vague_reassurance_examples='"I\'ll look into it", "I\'ll get that sorted"',
    farewell_re=re.compile(
        r"\b(goodbye|good bye|bye|take care|have a (good|nice) (day|one)|"
        r"speak (to you )?soon|talk to you later)\b",
        re.IGNORECASE,
    ),
    postpone_re=re.compile(
        r"(another time|some other time|call (you )?back|ring (you )?back|"
        r"get back to you|later (today|this week)|"
        r"no time (right now|at the moment|today)|"
        r"(have|need) to (go|run|hang up|dash)|wrap (this |it )?up|"
        r"end (the|this) call)",
        re.IGNORECASE,
    ),
    regreeting_re=re.compile(
        r"^[\s\"'>-]*(hello\b|hi\b|hey\b|good (morning|afternoon|evening)|"
        r"good day)",
        re.IGNORECASE,
    ),
    repeat_request_re=re.compile(
        r"(pardon\b|sorry,? what|come again|say (that|it) again|"
        r"who (are|is) (you|this|that)\b|who am i speaking|"
        r"what('?s| is| was) your name( again)?|"
        r"(could|can) you (please )?repeat|repeat (that|it)|(one|once) more time|"
        r"(did|could)n'?t (quite )?(catch|hear|get) (that|you|what)|"
        r"missed (that|what you said))",
        re.IGNORECASE,
    ),
    closing_veto_re=re.compile(r"\bnot\b|n'?t\b|\bnever\b|\bbefore\b", re.IGNORECASE),
    still_pressing_re=re.compile(
        r"\b(i (want|need|must|expect|require)\b|when (will|is|does|can)\b|i'?m (still )?waiting\b)",
        re.IGNORECASE,
    ),
    stt_phantom_re=re.compile(
        r"^\W*(thank you( for watching)?|thanks for watching|amen|subtitles? by [\w\s,.-]+|"
        r"copyright [\w\s,.-]+)\W*$",
        re.IGNORECASE,
    ),
    open_question_re=re.compile(
        r"^(?:(?:and|but|so|okay|well|now)[\s,]+){0,2}"
        r"(whose|whom|who|what|when|where|why|which|how)\b",
        re.IGNORECASE,
    ),
    # Not "like": far more often a verb or a preposition than a filler.
    filler_re=re.compile(
        r"\b(basically|literally|actually|kind\s+of|sort\s+of|you\s+know|i\s+mean|"
        r"so\s+to\s+speak)\b",
        re.IGNORECASE,
    ),
    greeting_re=re.compile(r"\b(hello|hi|good\s+(morning|afternoon|evening))\b", re.IGNORECASE),
    # German has no safe "ich bin X": nouns are capitalised ("ich bin Kunde").
    self_intro_re=re.compile(
        r"\bmy\s+name\s+is\s+(?-i:[A-Z])|\bthis\s+is\s+(?-i:[A-Z])|\b(?-i:[A-Z])\w+\s+speaking\b"
        r"|\bi(?:'m|\s+am)\s+(?-i:[A-Z])"
        r"|\byou(?:'re|\s+are)\s+speaking\s+(?:with|to)\s+(?-i:[A-Z])",
        re.IGNORECASE,
    ),
    offer_re=re.compile(
        r"\b(how\s+(can|may)\s+i\s+(help|assist)|what\s+can\s+i\s+do\s+for\s+you"
        r"|what('s|\s+is)\s+(it|this)\s+about)",
        re.IGNORECASE,
    ),
    concern_re=re.compile(
        r"\b(i('m|\s+am)\s+calling\s+(about|because|regarding)"
        r"|the\s+reason\s+i('m|\s+am)\s+calling|it's\s+about)",
        re.IGNORECASE,
    ),
    recap_re=re.compile(
        r"\b(to\s+(sum\s+up|summari[sz]e|recap)|let\s+me\s+(just\s+)?(sum\s+up|summari[sz]e|recap)"
        r"|just\s+to\s+(recap|confirm)|in\s+summary"
        r"|(so\s+)?we('ve|\s+have)\s+(\w+\s+){0,2}(agreed|discussed|settled))",
        re.IGNORECASE,
    ),
    agreement_re=re.compile(
        r"\b(i('ll|\s+will)\s+(send|email|call|ring|book|confirm|forward|get\s+back)"
        r"|you('ll|\s+will)\s+(get|receive|hear)|next\s+step"
        r"|(we('ll|\s+will)|let's)\s+(go\s+with|leave\s+it)"
        r"|by\s+(monday|tuesday|wednesday|thursday|friday|tomorrow|the\s+end\s+of|next\s+week|\d))",
        re.IGNORECASE,
    ),
    sign_off_re=re.compile(
        r"\b(goodbye|good\s+bye|bye|take\s+care"
        r"|have\s+a\s+(good|nice|great|lovely)\s+(day|one|evening|weekend)"
        r"|thanks?(\s+you)?\s+(\w+\s+){0,2}for\s+(calling|your\s+time|the\s+call))",
        re.IGNORECASE,
    ),
    fallback_closing_line="Thank you for your time. Goodbye.",
    pickup_prompts=("Hello?", "Hello? Can you hear me?"),
)


LANGUAGE_PACKS: dict[str, LanguagePack] = {"de": _GERMAN, "en": _ENGLISH}


def get_pack(language_id: str) -> LanguagePack:
    """KeyError for a Persona without a pack: a configuration error."""
    return LANGUAGE_PACKS[language_id]
