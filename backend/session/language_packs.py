"""The parts of the prompt frame that cannot be English (ADR 0043).

Everything the model is *instructed* with is English and lives in
`orchestrator.py`. Three things resist that, and they are collected here,
keyed by the Persona's `language_id`:

* `example_exchange` demonstrates the register of a phone call in the target
  language rather than instructing the model, so translating it would make it
  demonstrate the wrong thing.
* `farewell_re` / `postpone_re` (ADR 0037) are matched against the *user's*
  transcribed speech, which is in the Persona's language, not English.
* `regreeting_re` (ADR 0038) is matched against the *Persona's* own reply, to
  catch it greeting or re-introducing itself after the call is already under
  way -- a greeting is a phrase in the spoken language, not English.
* `repeat_request_re` (ADR 0038) is matched against the *user's* speech: when
  the user asks the persona to say something again ("wer sind Sie nochmal?",
  "können Sie das wiederholen?"), repeating is the right answer, so that turn
  is exempt from every repetition guard.
* `fallback_closing_line` (ADR 0038) is spoken aloud to the user.
* `user_closing_examples` / `vague_reassurance_examples` quote phrases the
  *user* would say, so they only help the model recognise them if they are in
  the language the user is actually speaking.

Adding a language means adding one entry here plus a Persona row carrying that
`sprache_code`; Scenarios stay untouched.
"""

import re
from dataclasses import dataclass

# Clause boundaries. The veto below only looks back to the nearest one, because
# a negation belongs to its own clause: "Ich kann nicht länger warten, auf
# Wiederhören" really is a goodbye, while "sagen Sie nicht einfach tschüss" is
# not, and the comma is what separates the two.
_CLAUSE_END_RE = re.compile(r"[,;.!?]")


@dataclass(frozen=True)
# A configuration record, not an object with behaviour: one field per thing
# about a language that cannot be English. Splitting it to satisfy the limit
# would scatter what belongs together.
# pylint: disable=too-many-instance-attributes
class LanguagePack:
    """Everything about one supported conversation language."""

    # The language's English name, interpolated into the English prompt frame.
    name_en: str
    # Two short exchanges demonstrating register, sentence length and pacing in
    # the target language -- never how a call should unfold. Four constraints
    # shape them. They start mid-call and show no opening, because openings are
    # what `opening_examples` is for: a second, smaller pool of opening lines
    # here competes with it, and the model drew a name out of the smaller one
    # ("Ostermann mein Name" reached a call whose Persona was called something
    # else). For the same reason they name nobody at all. They sit in a domain
    # no Scenario uses, because an example close to a Scenario's own subject
    # gets reused as content instead of read as form. And they stay concrete,
    # naming a date and a number, because that is the behaviour the frame asks
    # for and a vague example would demonstrate the opposite.
    example_exchange: str
    # Several structurally different ways to open a call, in the target
    # language. The frame used to carry a single English one ('e.g. "Hi, this
    # is..."'), which the model copied verbatim into every opening -- including
    # into German calls, producing "Hi, this is Thomas Brandt, ich habe eine
    # Frage...". Several varied openers spread that distribution; one anchor
    # collapses it.
    opening_examples: str
    # The same, for a reverse (ADR 0070), where the Persona picks up instead of
    # calling: several ways to answer a phone. A separate pool rather than a
    # note on `opening_examples`, for the reason that field's comment gives --
    # the model copies the shape of whatever examples it is shown, and an
    # answering line and an opening line are different shapes. They say nothing
    # about any case, because a callee who names one has invented the caller's
    # reason before hearing it.
    answering_examples: str
    # Quoted user phrases the English frame points at, in the target language.
    user_closing_examples: str
    vague_reassurance_examples: str
    farewell_re: re.Pattern[str]
    postpone_re: re.Pattern[str]
    # Matched against the start of the Persona's own reply: the small model
    # tends to restart the call from the top -- greeting again, name again --
    # when it has run low on new things to say (ADR 0038). Anchored, because it
    # is only a re-introduction when it is the *opening* of the reply.
    regreeting_re: re.Pattern[str]
    # Matched against the user's speech: an explicit "say that again" / "who
    # are you?" makes repeating the correct move, so the turn is exempt from
    # the repetition guards (ADR 0038).
    repeat_request_re: re.Pattern[str]
    # Words that, standing in the same clause as a matched farewell or
    # postponement, mean the phrase is being *talked about* rather than used:
    # a negation ("sagen Sie nicht einfach tschüss"), or a marker putting it in
    # the future ("bevor wir auf Wiederhören sagen, hätte ich noch eine
    # Frage"). Both were observed to end a call the user was still in the
    # middle of, which is the expensive direction of error -- a missed signal
    # costs one extra turn, a false one cuts the conversation off.
    closing_veto_re: re.Pattern[str]
    # Matched against the *persona's* last sentence when it carries an
    # unprompted [CALL_END] (ADR 0037): a demand or an open question there
    # means the model lost the thread, not that the call is over. Narrow, like
    # the user-side patterns, and a farewell in the same sentence overrides it.
    still_pressing_re: re.Pattern[str]
    # Whisper does not return an empty transcript on near-silence; it invents
    # a fixed phrase in the audio's language ("Vielen Dank.", "Amen.", a
    # subtitle credit). A whole transcript matching one of these is not a
    # Turn (docs/research/model-parameters.md; ADR 0071). Whole-message
    # patterns only: "Nein, danke, das passt" is a real answer.
    stt_phantom_re: re.Pattern[str]
    # A question word at the start makes an open question, anything else a
    # closed one. Anchored, and deliberately shallow: a question word buried
    # further in counts as closed rather than being guessed at.
    open_question_re: re.Pattern[str]
    # Lexical fillers only: real words, so they survive transcription. Hesitation
    # sounds ("äh") do not -- Whisper drops them -- and so are not listed.
    filler_re: re.Pattern[str]
    # The three parts of an opening turn (F-63). The name is unknown, so
    # self_intro_re looks for the frames it is said in, followed by a capital.
    greeting_re: re.Pattern[str]
    self_intro_re: re.Pattern[str]
    # The third part depends on who rang: the called side offers help, the
    # caller states the concern (a reverse, ADR 0070).
    offer_re: re.Pattern[str]
    concern_re: re.Pattern[str]
    fallback_closing_line: str


# Whisper's non-speech annotations -- "*Titelm*", "[Musik]", "(Applaus)" -- are
# language-independent; the phantom phrases are per pack.
_ANNOTATION_RE = re.compile(r"^\s*[*\[(][^*\]\)]*[*\])]\s*[.!?]*\s*$")


def is_phantom(pack: LanguagePack, user_text: str) -> bool:
    """True if the transcript is Whisper inventing speech on near-silence -- a
    VAD misfire, not a Turn (ADR 0071)."""
    stripped = user_text.strip()
    return not stripped or bool(_ANNOTATION_RE.match(stripped)) or bool(pack.stt_phantom_re.match(stripped))


def signals_closing(pack: LanguagePack, user_text: str) -> bool:
    """True if the user really signalled the call is over.

    A bare `search` is not enough: these phrases also appear as the object of a
    sentence rather than as its act -- "sagen Sie nicht einfach tschüss", "bevor
    wir auf Wiederhören sagen, hätte ich noch eine Frage". So a match only
    counts when its own clause does not veto it.
    """
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
    # Catches an explicit farewell or a request to postpone/continue elsewhere --
    # the two categories of user signal the persona's own judgment (the system
    # prompt) was observed to miss. Deliberately narrow and regex-based, not an
    # LLM classifier: that approach's own chain-of-thought reasoning would
    # occasionally degenerate into a non-sequitur and land on the wrong verdict
    # (confirmed in testing). A missed signal here just costs one extra turn; a
    # false one cuts the call short mid-conversation, which is worse.
    farewell_re=re.compile(
        r"\b(tschüss|auf wiederhören|auf wiedersehen|wiederhören|ciao)\b", re.IGNORECASE
    ),
    postpone_re=re.compile(
        r"(ein andere[rs]? mal|andermal|anders (fortsetzen|weiterführen|weitermachen)|"
        r"später (nochmal|weiter|zurückrufen)|melde mich (nochmal|später|wieder)|"
        # "keine Zeit mehr *für* X" is a complaint about X, not a request to
        # hang up -- and complaint Scenarios are exactly where it turns up.
        r"rufe? (sie |dich )?(nochmal|später|zurück)|keine zeit (mehr|gerade)\b(?!\s*f(ü|ue)r)|"
        r"muss (jetzt |gleich )?(auflegen|los|schluss machen)|gespräch (beenden|abbrechen)|"
        # The inflected forms -- "ich beende das Gespräch jetzt", "ich lege
        # jetzt auf" -- were said to the persona and missed. The look-ahead
        # keeps "ich beende das Gespräch nicht" out, since the veto only reads
        # the clause *before* a match.
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
        # Not followed by a reason clause: "das habe ich nicht verstanden" asks
        # for a repeat, "ich kann nicht verstehen, warum ..." is an objection to
        # the substance and must not put the persona into repeat mode.
        r"nicht (ganz |richtig |gut |so )?(verstanden|verstehen|mitbekommen|gehört|mitgekriegt)"
        r"\b(?!\s*,?\s*(warum|wieso|weshalb|dass))|"
        r"schlecht (zu )?(verstehen|verstanden|hören))",
        re.IGNORECASE,
    ),
    closing_veto_re=re.compile(
        r"\b(nicht|kein\w*|nie|niemals|bevor|ehe)\b", re.IGNORECASE
    ),
    # "Ich will wissen, wann ..." / "Ich muss wissen ..." / "Wann wird ..." --
    # the shapes the persona's demands took in the calls that ended on them.
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
    # Longest alternatives first, so "womit" is not shadowed by "wo"; leading
    # fillers are skipped ("Und was brauchen Sie?").
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
    # "hier ist Schmidt", not "hier ist alles" or "hier ist Ihr Ansprechpartner".
    self_intro_re=re.compile(
        r"\bmein\s+name\s+ist\s+(?-i:[A-ZÄÖÜ])"
        r"|\bhier\s+(?:ist|spricht)\s+(?!ihr\b|ihre\b|sie\b)(?-i:[A-ZÄÖÜ])"
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
    fallback_closing_line="Vielen Dank für Ihre Zeit. Auf Wiederhören.",
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
    # Same rationale as the German patterns above: narrow, regex-based, and
    # matched against the user's own transcribed speech.
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
    # "I'm Alice" is the commonest of them. German has no safe equivalent:
    # nouns are capitalised, so "ich bin Kunde" would pass for a name.
    self_intro_re=re.compile(
        r"\bmy\s+name\s+is\s+(?-i:[A-Z])|\bthis\s+is\s+(?-i:[A-Z])|\b(?-i:[A-Z])\w+\s+speaking\b"
        r"|\bi(?:'m|\s+am)\s+(?-i:[A-Z])",
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
    fallback_closing_line="Thank you for your time. Goodbye.",
)


LANGUAGE_PACKS: dict[str, LanguagePack] = {"de": _GERMAN, "en": _ENGLISH}


def get_pack(language_id: str) -> LanguagePack:
    """The pack for this language.

    Raises KeyError for a Persona whose `sprache_code` has no pack — a
    configuration error worth failing loudly on rather than silently running
    the call with the wrong language's closing detection.
    """
    return LANGUAGE_PACKS[language_id]
