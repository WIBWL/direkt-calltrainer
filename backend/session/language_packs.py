"""The parts of the prompt frame that cannot be English (ADR 0043).

Everything the model is *instructed* with is English and lives in
`orchestrator.py`. Three things resist that, and they are collected here,
keyed by the Persona's `language_id`:

* `example_exchange` demonstrates the register of a phone call in the target
  language rather than instructing the model, so translating it would make it
  demonstrate the wrong thing.
* `farewell_re` / `postpone_re` (ADR 0037) are matched against the *user's*
  transcribed speech, which is in the Persona's language, not English.
* `fallback_closing_line` (ADR 0038) is spoken aloud to the user.
* `user_closing_examples` / `vague_reassurance_examples` quote phrases the
  *user* would say, so they only help the model recognise them if they are in
  the language the user is actually speaking.

Adding a language means adding one entry here plus a Persona row carrying that
`sprache_code`; Scenarios stay untouched.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LanguagePack:
    """Everything about one supported conversation language."""

    # The language's English name, interpolated into the English prompt frame.
    name_en: str
    example_exchange: str
    # Several structurally different ways to open a call, in the target
    # language. The frame used to carry a single English one ('e.g. "Hi, this
    # is..."'), which the model copied verbatim into every opening -- including
    # into German calls, producing "Hi, this is Thomas Brandt, ich habe eine
    # Frage...". Several varied openers spread that distribution; one anchor
    # collapses it.
    opening_examples: str
    # Quoted user phrases the English frame points at, in the target language.
    user_closing_examples: str
    vague_reassurance_examples: str
    farewell_re: re.Pattern[str]
    postpone_re: re.Pattern[str]
    fallback_closing_line: str


_GERMAN = LanguagePack(
    name_en="German",
    example_exchange=(
        "Example of the register, sentence length and pacing to aim for — this "
        "says nothing about how a call should unfold, only how it should "
        "sound. Invent your own content that fits YOUR actual scenario and "
        "character; never reuse this text or its specifics. The dialogue is in "
        "the language you must speak:\n"
        '[Caller opens] "Guten Tag, hier ist Frau Beck von der Buchhaltung, '
        'ich habe eine Frage zu unserer letzten Rechnung."\n'
        '[Other person] "Guten Tag Frau Beck, worum geht es denn genau?"\n'
        '[Caller] "Wir wurden für März doppelt belastet, einmal am 3. und '
        'einmal am 17."\n'
        '[Other person] "Das schaue ich mir an. Können Sie mir die '
        'Rechnungsnummer nennen?"\n'
        '[Caller] "Die habe ich gerade nicht griffbereit, aber es war ein '
        'Betrag über 480 Euro."'
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
        r"rufe? (sie |dich )?(nochmal|später|zurück)|keine zeit (mehr|gerade)|"
        r"muss (jetzt |gleich )?(auflegen|los|schluss machen)|gespräch (beenden|abbrechen))",
        re.IGNORECASE,
    ),
    fallback_closing_line="Vielen Dank für Ihre Zeit. Auf Wiederhören.",
)


_ENGLISH = LanguagePack(
    name_en="English",
    example_exchange=(
        "Example of the register, sentence length and pacing to aim for — this "
        "says nothing about how a call should unfold, only how it should "
        "sound. Invent your own content that fits YOUR actual scenario and "
        "character; never reuse this text or its specifics. The dialogue is in "
        "the language you must speak:\n"
        '[Caller opens] "Good morning, this is Claire Hughes from accounts, '
        'I have got a question about our last invoice."\n'
        '[Other person] "Good morning Ms Hughes, what is it about exactly?"\n'
        '[Caller] "We were charged twice for March, once on the 3rd and once '
        'on the 17th."\n'
        '[Other person] "Let me look into that. Could you give me the invoice '
        'number?"\n'
        '[Caller] "I have not got it to hand, but it was around 480 pounds."'
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
