# Feature-Katalog

## Zweck und Abgrenzung

Dieser Katalog enthält ausschließlich **funktionale Anforderungen**, also das, was das System tut. Qualitätsziele, Randbedingungen und Nicht-Ziele sind bewusst nicht enthalten. Sie werden an anderer Stelle geführt.

## Gesprächssimulation und KI-Gegenpart

| ID | Feature | Kurzbeschreibung | ISO 25010 | Prio | Anforderung |
|---|---|---|---|---|---|
| F-01 | Live-Gesprächssimulation mit KI | Das System agiert im Telefonie-Kontext als Gesprächspartner und reagiert auf Inhalt und Gesprächsführung des Nutzers, einschließlich spontaner Einwände. | Funktionale Vollständigkeit | MUST | R-05, R-06, R-12 |
| F-03 | Szenario-Typen | Das System deckt mehrere Gesprächskontexte ab: kurze Support-Fälle, längere beratende Projektgespräche sowie Angebots- und Preisgespräche. | Funktionale Vollständigkeit | MUST | R-03, R-09, R-10 |
| F-04 | Kundenpersona-Bibliothek | Erweiterbare Auswahl an Gesprächspartnern mit unterschiedlicher Haltung, unter anderem kostenkritische Kunden sowie Geschäftsführer und IT-Leiter mit Fokus auf Strategie und Budget. | Funktionale Vollständigkeit | MUST | R-06, R-07, R-08 |
| F-23 | Mehrteilige Projektgespräche | Trainingsfälle erstrecken sich über mehrere Sitzungen, wobei sich der Gegenpart an vorangegangene Termine erinnert. | Funktionale Vollständigkeit | COULD | R-11 |
| F-34 | Usergesteuertes Szenario | Der Nutzer beschreibt die zu trainierende Gesprächssituation per Freitext. | Funktionale Vollständigkeit | COULD | R-09 |

## Sprach- und Kommunikationsanalyse

| ID | Feature | Kurzbeschreibung | ISO 25010 | Prio | Anforderung |
|---|---|---|---|---|---|
| F-35 | Analyse der Intonation | Erfassung der Tonhöhenvariation, wodurch Monotonie sichtbar wird. | Funktionale Korrektheit | MUST | R-14 |
| F-36 | Analyse des Sprechtempos | Erfassung von Sprechtempo und Tempoverlauf, auch relativ zum Gesprächspartner. | Funktionale Korrektheit | MUST | R-14 |
| F-37 | Analyse der Lautstärke | Erfassung von Lautstärke und Lautstärkeschwankungen als Maß stimmlicher Präsenz. | Funktionale Korrektheit | MUST | R-14 |
| F-38 | Analyse der Artikulation | Erkennung undeutlich gesprochener Passagen. | Funktionale Korrektheit | MUST | R-14 |
| F-51 | Analyse der Sprechflüssigkeit | Erkennung von Stockungen, Füllwörtern und Unterbrechungen im Redefluss. | Funktionale Korrektheit | MUST | R-18 |
| F-08 | Erkennung überlanger oder überkomplexer Erklärungen | Erkennung zu hoher Informationsdichte und Redundanz sowie daraus entstehender Missverständnisse. | Funktionale Korrektheit | MUST | R-15, R-17 |
| F-40 | Analyse der sprachlichen Konkretheit | Erkennung des Anteils konkreter gegenüber vager oder stark fachsprachlicher Formulierungen. | Funktionale Korrektheit | SHOULD | R-16 |
| F-42 | Phasengerechte Sprache | Erkennung der Gesprächsphase und Bewertung der Passung des Sprachtons. | Funktionale Korrektheit | SHOULD | R-13 |
| F-24 | Analyse der Redeanteile | Ermittlung der Sprechzeitverteilung, bewertet relativ zum Gesprächstyp. | Funktionale Korrektheit | SHOULD | R-14 |
| F-41 | Erkennung aktiven Zuhörens | Erkennung von Pausen, bestätigenden Signalen und zusammenfassenden Rückgriffen. | Funktionale Korrektheit | SHOULD | R-14 |
| F-39 | Kongruenz von Inhalt und Stimme | Abgleich der stimmlichen Umsetzung mit dem verbalen Inhalt. | Funktionale Korrektheit | COULD | R-19 |

## Feedback und Auswertung

| ID | Feature | Kurzbeschreibung | ISO 25010 | Prio | Anforderung |
|---|---|---|---|---|---|
| F-09 | Qualitatives Wrap-up | Zusammenfassende Rückmeldung nach dem Gespräch, mehrdimensional und ohne Reduktion auf einen Zahlenwert. | Funktionale Vollständigkeit | MUST | R-19, R-20 |
| F-10 | Konkrete Verbesserungsvorschläge | Unmittelbar anwendbare Hinweise mit Bezug auf konkrete Gesprächsstellen. | Funktionale Vollständigkeit | MUST | R-22 |
| F-52 | Leitfadenbasierte Bewertung | Verbesserungsvorschläge orientieren sich an einem hinterlegten Gesprächsleitfaden des Anwenderunternehmens. | Funktionale Vollständigkeit | COULD | R-23, R-43 |
| F-53 | Auswertungs-Dashboard | Visuelle Darstellung der Auswertung im Stil eines Dashboards. | Funktionale Vollständigkeit | SHOULD | R-24 |
| F-47 | Verknüpfung von Feedback und Gesprächsstellen | Hinweise sind über Zeitmarken mit Transkript und Aufzeichnung verknüpft. | Funktionale Vollständigkeit | COULD | R-22 |
| F-14 | Score für das Gespräch | Ergänzender Zahlenwert zur groben Orientierung, kein Ersatz für das Feedback. | Funktionale Vollständigkeit | COULD | R-21 |
| F-54 | Gesprächszusammenfassung für den Gesprächspartner | Erzeugung einer Zusammenfassung, mit der das gemeinsame Verständnis abgesichert werden kann. | Funktionale Vollständigkeit | COULD | R-31 |

## Lernprozess und Reflexion

| ID | Feature | Kurzbeschreibung | ISO 25010 | Prio | Anforderung |
|---|---|---|---|---|---|
| F-12 | Aufzeichnung des Gesprächs | Aufzeichnung und Transkription zur nachträglichen Reflexion. | Funktionale Vollständigkeit | SHOULD | R-28 |
| F-13 | Aufzeichnung des Fortschritts | Nutzerbezogene Verlaufsdaten über längere Zeiträume, nachvollziehbar dargestellt. | Funktionale Vollständigkeit | SHOULD | R-29, R-30 |
| F-48 | Trainingshistorie | Übersicht vergangener Trainings, filterbar nach Szenario-Typ und Zeitraum. | Funktionale Vollständigkeit | COULD | R-29 |

## Bedienoberfläche

| ID | Feature | Kurzbeschreibung | ISO 25010 | Prio | Anforderung |
|---|---|---|---|---|---|
| F-43 | Setup-Übersicht | Startbildschirm mit sichtbaren Pflichteinstellungen, Zusatzoptionen eingeklappt. | Interaktionsfähigkeit | MUST | R-34 |
| F-46 | Live-Call-Interface | Bedienoberfläche während des Gesprächs mit Mikrofonstatus, Dauer und Beenden-Funktion. | Interaktionsfähigkeit | MUST | R-05, R-32 |
| F-44 | Persona-Kartenansicht | Auswahl der Persona über Karten mit Kurzsteckbrief. | Interaktionsfähigkeit | SHOULD | R-07, R-08 |
| F-45 | Wissensbasis-Upload-Oberfläche | Oberfläche zum Hochladen und Verwalten eigener Dokumente. | Interaktionsfähigkeit | SHOULD | R-42, R-43 |

## Konto und Zugriff

| ID | Feature | Kurzbeschreibung | ISO 25010 | Prio | Anforderung |
|---|---|---|---|---|---|
| F-31 | Accountsystem | Nutzerbezogene Datenhaltung für Aufzeichnungen, Feedback und Trainingsverlauf. | Sicherheit | MUST | C-04 |
| F-50 | Login und Authentifizierung | Anmeldung über Benutzername und Passwort, der Zugriff auf nutzerbezogene Daten ist erst danach möglich. | Sicherheit | MUST | C-04 |
| F-49 | Datenschutzhinweis beim Start | Hinweis zu Art, Zweck und Ort der Datenverarbeitung vor der ersten Aufzeichnung. | Sicherheit | MUST | C-04 |

## Integration und Wissensanbindung

| ID | Feature | Kurzbeschreibung | ISO 25010 | Prio | Anforderung |
|---|---|---|---|---|---|
| F-26 | Kundenspezifische Wissensbasis | Nutzer stellen eigene Dokumente und Gesprächsleitfäden bereit, die den fachlichen Rahmen prägen. | Funktionale Vollständigkeit | SHOULD | R-42, R-43 |
| F-29 | Anbindung an die Telefonsoftware Starface | Integration mit dem im Unternehmen genutzten Telefoniesystem. | Kompatibilität | COULD | R-38 |
| F-55 | Auswertung realer Kundengespräche | Mitlaufen und Auswerten echter Telefonate statt ausschließlich simulierter Gespräche. | Funktionale Vollständigkeit | COULD | R-44 |

## Multimodale Erweiterung

| ID | Feature | Kurzbeschreibung | ISO 25010 | Prio | Anforderung |
|---|---|---|---|---|---|
| F-32 | Videobasierte Verarbeitung | Verarbeitung von Videosignalen zur Abbildung von Konferenzkanälen. | Funktionale Vollständigkeit | COULD | R-39 |
| F-33 | Analyse der visuellen nonverbalen Kommunikation | Auswertung von Mimik und Gestik auf Basis des Videosignals. | Funktionale Korrektheit | COULD | R-14 |

## Verteilung

| Prio | Anzahl |
|---|---|
| MUST | 16 |
| SHOULD | 11 |
| COULD | 11 |
| **Gesamt** | **38** |

## Neu aufgenommene Features

| ID | Feature | Anlass |
|---|---|---|
| F-51 | Analyse der Sprechflüssigkeit | R-18, APPOLLO Systems: Flüssigkeit gilt als zentraler Erfolgsmaßstab |
| F-52 | Leitfadenbasierte Bewertung | R-23, R-43, APPOLLO Systems: Verbesserungsvorschläge am internen Leitfaden |
| F-53 | Auswertungs-Dashboard | R-24, APPOLLO Systems: visuelle Darstellung der Auswertung |
| F-54 | Gesprächszusammenfassung für den Gesprächspartner | R-31, Solox: Absicherung des gemeinsamen Verständnisses |
| F-55 | Auswertung realer Kundengespräche | R-44, APPOLLO Systems: Mitlaufen echter Telefonate |

## Offene Punkte

- **K-01 wirkt unmittelbar auf F-03.** Solox lehnt einen vertrieblichen Fokus ab, APPOLLO Systems fordert Angebots- und Preisgespräche. Die Beschreibung von F-03 nimmt beides auf. Ob das so bleibt, hängt an der Entscheidung zu K-01.
- **R-04 hat kein Feature.** Dass die Entscheidungsbefugnis der Nutzer begrenzt ist, sollte sich im Verhalten des Gegenparts widerspiegeln. Ob das ein eigenes Feature wird oder eine Eigenschaft von F-03 und F-04, ist offen.
- **Die Release-Zuordnung ist zu überprüfen.** Die bisherige Version-1.0-Auswahl entstand vor der Zusammenführung und vor den neuen Features. Priorität und Release sind getrennte Dimensionen und sollten in einer eigenen Spalte geführt werden, sobald der Zuschnitt steht.
- **F-52 und F-26 überschneiden sich.** F-26 stellt Dokumente bereit, F-52 nutzt sie zur Bewertung. Die Trennung sollte in den Beschreibungen deutlicher werden.
