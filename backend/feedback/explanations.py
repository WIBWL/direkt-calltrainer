"""The text behind each metric's "i", one per active metric (ADR 0098), served by
`readings.py` and never copied into the frontend. Texts explaining a *scale* stay
beside their thresholds (ADR 0078). Each says what is counted, how, what it is
worth and where it stops being trustworthy: no figure has a target (ADR 0004/0051).
"""

TALK_SHARE = (
    "Ihr Anteil an der Zeit, in der überhaupt gesprochen wurde. Gerechnet wird "
    "mit Sprechzeit und nicht mit der Uhr: Was die Technik zum Antworten "
    "braucht, zählt für keine Seite mit. Ihre Seite ist die Länge Ihrer "
    "Aufnahmen, die andere die Länge der ausgegebenen Antworten. "
    "Einen richtigen Wert gibt es nicht. In einer Beratung, in der Sie "
    "erklären, steht hier zu Recht etwas anderes als in einer Reklamation, in "
    "der Sie zuhören. "
    "Bedenken Sie außerdem, dass Ihr Gegenüber eine synthetische Stimme mit "
    "fest eingestelltem Tempo ist. Der Anteil beschreibt deshalb Ihr Gespräch "
    "und nicht das Verhalten der anderen Seite."
)

QUESTIONS = (
    "Gezählt werden die Fragezeichen in dem, was Sie gesagt haben. Die "
    "Spracherkennung setzt im Deutschen zuverlässig genug Satzzeichen; eine "
    "Liste von Fragewörtern würde die Umstellung übersehen, die im Deutschen "
    "die meisten Fragen trägt („Können Sie mir sagen …“). "
    "Offene und geschlossene Fragen werden an denselben Fragezeichen "
    "abgelesen, die beiden Zahlen ergeben also immer die Gesamtzahl. "
    "Wie viele Fragen angemessen sind, hängt vom Gespräch ab. Hier wird "
    "gezählt und nicht bewertet. "
    "Eine Frage, die Sie wie eine Aussage gesprochen haben, fehlt in dieser "
    "Zahl, weil das Transkript dort kein Fragezeichen setzt."
)

PACE = (
    "Wörter je Minute reiner Sprechzeit. Geteilt wird durch die Zeit, in der "
    "Sie tatsächlich gesprochen haben, nicht durch die Länge der Aufnahme: "
    "Pausen innerhalb Ihrer Beiträge und die Stille, die vorn und hinten "
    "mitgeschnitten wird, stehen nicht im Nenner. "
    "Deshalb liegt diese Zahl höher als ein Tempo, das über die ganze "
    "Gesprächszeit gerechnet ist, und lässt sich mit Werten aus anderen "
    "Anwendungen nicht vergleichen. "
    "Ein passendes Tempo gibt es nicht als Zahl. Was angenehm ist, hängt von "
    "Anlass, Thema und Gegenüber ab. Lesen Sie die Zahl gegen Ihre eigenen "
    "anderen Gespräche."
)

WORD_COUNT = (
    "Alle Wörter Ihrer Beiträge, dazu die Zahl Ihrer Sätze und die "
    "durchschnittliche Satzlänge. "
    "Für sich genommen sagt die Summe vor allem, wie lang das Gespräch war. "
    "Ihren Wert hat sie als Maßstab für die Zählwerte daneben: Füllwörter, "
    "Wiederholungen und Fragen haben in einem langen Gespräch mehr "
    "Gelegenheit. "
    "Die Satzlänge ist die beobachtbare Spur eines überladenen Satzes. Ob er "
    "überladen war, steht in der Auswertung und nicht in dieser Zahl."
)

FILLERS = (
    "Gezählt werden echte Wörter, die die Spracherkennung überstanden haben: "
    "„quasi“, „sozusagen“, „eigentlich“ und ihresgleichen. Welche es in diesem "
    "Gespräch waren, steht unten. "
    "Verzögerungslaute wie „äh“ sind hier nicht dabei. Die Spracherkennung "
    "schreibt sie gar nicht erst mit, eine Null sagt an dieser Stelle also "
    "nichts über „äh“. Dafür gibt es die Kennzahl Verzögerungslaute, die aus "
    "dem Klang gelesen wird. "
    "Ein Füllwort ist kein Fehler. Auffällig wird erst die Häufung, und ab "
    "wann sie auffällt, ist nirgends belegt."
)

OPENING = (
    "Geprüft wird Ihr erster Beitrag auf drei Teile: eine Begrüßung, Ihren "
    "Namen und, je nachdem wer angerufen hat, das Angebot zu helfen oder Ihr "
    "eigenes Anliegen. "
    "Erkannt werden sie an ihrer Einkleidung („hier ist“, „mein Name ist“, "
    "„am Apparat“). Ein bloßer Nachname bleibt deshalb unerkannt. „Nicht "
    "erkannt“ heißt hier also nicht „hat gefehlt“. "
    "Daneben steht Ihr Sprechtempo im ersten Beitrag im Verhältnis zum Rest "
    "des Gesprächs. "
    "Eine Note ist das nicht. Drei erkannte Teile sind kein besseres Gespräch "
    "als zwei."
)

CLOSING = (
    "Geprüft werden Ihre letzten beiden Beiträge auf drei Teile: eine "
    "Zusammenfassung, eine konkrete Verabredung und einen Abschied. "
    "Zwei Beiträge, weil die Zusammenfassung meist einen Zug vor dem Abschied "
    "kommt und der letzte Beitrag oft nur noch „Auf Wiederhören“ ist. "
    "Als Verabredung zählt etwas Nachprüfbares, also ein Termin oder ein "
    "benannter nächster Schritt. Eine vage Zusicherung wie „ich kümmere mich "
    "darum“ zählt nicht mit. "
    "Unter drei Beiträgen im ganzen Gespräch wird nicht geprüft, weil das "
    "Fenster sonst bis in den Einstieg zurückreichen würde. Geprüft wird "
    "dasselbe, gleich wer angerufen hat: Ein Gespräch gut zu beenden verlangt "
    "von beiden Seiten dasselbe."
)

REPETITIONS = (
    "Gezählt werden Passagen von vier Wörtern oder mehr, die später im "
    "Gespräch wörtlich noch einmal vorkommen. Vier, damit ein wiederholtes "
    "„ich habe das“ nicht zählt, ein wiederholter Satz aber schon. "
    "Überlappende Treffer werden zusammengezogen, ein zweimal gesagter Satz "
    "zählt also einmal. "
    "Wiederholung ist nicht von sich aus schlecht. Wer etwas Wichtiges noch "
    "einmal sagt, tut das meist mit Absicht. Die gefundenen Passagen stehen "
    "unten, damit Sie selbst sehen, was gezählt wurde."
)

HESITATIONS = (
    "Diese Zahl kommt aus dem Klang und nicht aus dem Text: gezählt wird ein "
    "gehaltener Laut von mindestens einer Viertelsekunde, dessen Tonhöhe sich "
    "dabei kaum bewegt. So klingt ein „ähm“. "
    "Über das Transkript ginge es nicht, weil die Spracherkennung "
    "Verzögerungslaute wegräumt. "
    "Es ist eine Schätzung. Ein gedehntes „jaaa“ hat dieselbe Form und wird "
    "mitgezählt, und beide Schwellen sind vorläufig gewählt und noch nicht "
    "gegen echte Aufnahmen geprüft."
)

REACTION_TIME = (
    "Die Zeit zwischen dem Verstummen Ihres Gegenübers und Ihrem ersten Laut, "
    "über das Gespräch gemittelt. "
    "Was die Technik zum Zuhören, Denken und Sprechen braucht, liegt außerhalb "
    "dieses Fensters. Ein langsamer Server kann hier also nicht wie Zögern "
    "aussehen. "
    "Enthalten ist dagegen der Moment, den Ihr Browser braucht, um das "
    "Einsetzen Ihrer Stimme zu erkennen. Die Zahl ist deshalb eher etwas zu "
    "groß als zu klein und am ehesten gegen Ihre eigenen anderen Gespräche zu "
    "lesen. "
    "Eine kurze Pause vor der Antwort ist nicht von sich aus besser als eine "
    "lange. Wer nachdenkt, bevor er auf einen Einwand antwortet, braucht sie."
)

PAUSES = (
    "Die mittlere Länge einer Stille innerhalb Ihrer eigenen Beiträge. "
    "Gezählt werden nur Pausen innerhalb einer Äußerung. Wird die Pause so "
    "lang, dass die Aufnahme endet, gilt sie als Ende Ihres Beitrags und "
    "taucht stattdessen in der Reaktionszeit auf. "
    "Als Stille gilt, was mindestens 25 Dezibel unter Ihrer lautesten Stelle "
    "liegt. In einer Aufnahme mit Störgeräusch findet dieses Verfahren keine "
    "Stille, und dann wird diese Kennzahl gar nicht erst gezeigt. "
    "Pausen sind kein Mangel. Sie geben dem Gegenüber die Gelegenheit "
    "einzusteigen."
)

PHONATION_SHARE = (
    "Der Anteil Ihrer eigenen Aufnahme, in dem Sie tatsächlich gesprochen "
    "haben, statt zu pausieren. "
    "Die Zahl liegt systematisch unter hundert Prozent: Die Aufnahme beginnt "
    "kurz vor Ihrem ersten Laut und endet kurz nach Ihrem letzten, und diese "
    "Ränder stehen im Nenner. "
    "Lesen Sie sie deshalb nur gegen Ihre eigenen anderen Gespräche und nicht "
    "gegen einen Wert von außen. "
    "Wie die Sprechpausen beruht sie darauf, Stille von Sprache zu trennen, "
    "und fehlt bei einer verrauschten Aufnahme ganz."
)

LOUDNESS = (
    "Die Zahl ist eine Spanne und kein Pegel: der Abstand zwischen Ihren "
    "leisesten und Ihren lautesten üblichen Stellen, in Dezibel. "
    "Ein Pegel würde vor allem Ihr Mikrofon und Ihren Abstand dazu messen. "
    "Auch die Spanne hängt noch daran, weshalb sie in keiner Auswertung über "
    "mehrere Gespräche hinweg auftaucht. "
    "Innerhalb dieses einen Gesprächs ist dafür der Verlauf lesbar, weil das "
    "Mikrofon dabei dasselbe geblieben ist: Sie sehen, wo Sie lauter und wo "
    "Sie leiser geworden sind."
)

# Moved here from `metrics.py`, where it sat beside its derivation, when twelve
# more of these were written: a text explaining one figure belongs with the
# other twelve rather than alone in the module that computes it.
RUN_LENGTH = (
    "Gemessen wird, wie lange Sie am Stück sprechen, bevor Sie absetzen. Ihre "
    "reine Sprechzeit geteilt durch die Anzahl Ihrer Sprechabschnitte. Als "
    "Abschnitt zählt alles zwischen zwei Pausen ab einer Viertelsekunde "
    "innerhalb einer Äußerung; eine längere Unterbrechung beendet die Äußerung "
    "und taucht stattdessen in der Reaktionszeit auf. "
    "Diese Zahl beschreibt als einzige hier das Sprechen selbst und nicht die "
    "Stille dazwischen. Zwei Menschen können denselben Redefluss und dieselbe "
    "mittlere Pausenlänge haben und trotzdem sehr verschieden klingen: der eine "
    "spricht in Zwei-Wort-Häppchen, der andere in ganzen Sätzen. Genau das "
    "steht hier. "
    "Eine Einordnung gibt es bewusst nicht. In der Forschung hängt dieses Maß "
    "eng damit zusammen, wie lebendig Zuhörer jemanden finden, enger sogar als "
    "die Tonhöhenschwankung. Ein Zusammenhang ist aber kein Grenzwert, und es "
    "ist nirgends belegt, ab wann ein Abschnitt zu kurz ist. Wie lang er sein "
    "sollte, hängt außerdem vom Gespräch ab: wer zuhört und kurz bestätigt, "
    "spricht zu Recht in kurzen Abschnitten. "
    "Vergleichen Sie die Zahl deshalb nur mit Ihren eigenen anderen Gesprächen. "
    "Weil wir schon ab einer Viertelsekunde trennen, fallen die Abschnitte "
    "kürzer aus als in Veröffentlichungen zu diesem Maß, die meist später "
    "trennen."
)
