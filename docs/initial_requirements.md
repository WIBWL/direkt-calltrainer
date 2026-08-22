# Anforderungsliste

**Stand:** Entwurf

**Geltungsbereich:** Anforderungen aus den bisher durchgeführten Erhebungen mit Solox und APPOLLO Systems, bestehend aus den Erstgesprächen und dem schriftlichen Rückfragenlauf vom 21.08.2026

| Erhebung                        | Kürzel | Datum      | Ansprechpartner |
| :------------------------------ | :----- | :--------- | :-------------- |
| Erstgespräch Solox GmbH         | `SO`   | 24.06.2026 | Nicolas Heyne   |
| Erstgespräch APPOLLO Systems    | `AP`   | 22.07.2026 | Eckhard Herdt   |
| Schriftverkehr Solox GmbH       | `SO-S` | 21.08.2026 | Nicolas Heyne   |
| Schriftverkehr APPOLLO Systems  | `AP-S` | 21.08.2026 | Eckhard Herdt   |

## Zweck

Diese Liste bildet die oberste Ebene der Anforderungsdokumentation. Sie hält fest, *welcher Bedarf* erhoben wurde, noch bevor entschieden ist, ob daraus ein Feature, ein Qualitätsziel oder eine Randbedingung wird.

Die Formulierung erfolgt in Bedarfssprache.

Sie ist zugleich die Quelle, aus der die nachgelagerte Dokumentation hervorgeht: Features, Qualitätsziele, Randbedingungen und Nicht-Ziele werden aus dieser Liste abgeleitet und nicht unabhängig davon aufgestellt. Jeder dieser Einträge soll sich auf eine Anforderung mit R-Nummer zurückführen lassen. Umgekehrt soll jede Anforderung entweder abgeleitet oder als offener Punkt ausgewiesen sein. Was sich nicht zurückführen lässt, ist in *Nicht aus den Erhebungen belegt* zu führen und als solches kenntlich zu machen.

| Typ           | Kürzel | Ziel                                   |
| :------------ | :----- | :------------------------------------- |
| Funktion      | F      | Feature-Katalog und Anforderungsbaum   |
| Qualitätsziel | Q      | arc42, Kapitel 10 (Qualitätsszenarien) |
| Randbedingung | C      | arc42, Kapitel 2                       |
| Nicht-Ziel    | N      |           |

## Referenzschema

Verwiesen wird nach dem Muster `SO <Kapitel>.<Frage>` beziehungsweise `AP <Kapitel>.<Frage>`. Die Fragennummer ergibt sich aus der bestehenden Reihenfolge im jeweiligen Protokoll. So bezeichnet `SO 4.5` die fünfte Frage in Kapitel 4. Eine Anpassung der Protokolle ist dafür nicht erforderlich.

Für den Schriftverkehr vom 21.08.2026 gilt das Muster `SO-S <Frage>` beziehungsweise `AP-S <Frage>`. Die Nummer bezeichnet den Fragenblock der Rückfragen-Mail:

| Nr. | Fragenblock                                         |
| :-- | :-------------------------------------------------- |
| 1   | Feedback nach dem Gespräch, insbesondere Kennzahlen |
| 2   | Sprache der Benutzeroberfläche                      |
| 3   | Transkript des Gesprächs                            |
| 4   | Gesprächssituationen und Kundenprofile              |
| 5   | Nutzergesteuerte Szenarien und Dokumenten-Upload    |

Anforderungen mit Quellenangaben aus beiden Unternehmen sind unabhängig belegt.

Die Spalte *Bezug* verweist auf das Element, das aus der Anforderung abgeleitet wurde: Feature-ID (`F-xx`), Qualitätsziel (`Q-xx`), Randbedingung (`C-xx`) oder Nicht-Ziel. Der Typ bestimmt den Zielort, siehe C-10.

Die Gegenrichtung führt der Feature-Katalog in der Spalte *Herkunft*. Dort können auch Features stehen, die aus dem Systementwurf statt aus einer Erhebung stammen und deshalb auf keine R-Nummer zurückgehen.

## Anforderungen

### Zielgruppe und Nutzungskontext

| ID   | Anforderung                                                                                                                                                                     | Quelle         | Typ | Bezug    |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------- | :-- | :------- |
| R-01 | Zur Zielgruppe gehören Personen mit direktem Kundenkontakt in Support- sowie in beratenden Projekt- und Entwicklungsrollen.                                                     | SO 4.1         | C   | C-07 |
| R-02 | Zur Zielgruppe gehören auch Personen mit technischem Hintergrund ohne vertriebliche Vorerfahrung.                                                                               | AP 3.1         | C   | C-07 |
| R-03 | Die Gesprächsdauern reichen von kurzen Rückfragen bis zu Gesprächen von einer Stunde.                                                                                           | SO 4.6, AP 3.6 | C   | C-06, Q-06, F-03     |
| R-04 | Die Entscheidungsbefugnis der Nutzer ist in manchen Fällen nicht ausreichend, sodass insbesondere im Support und bei technischen Fragen teilweise Rücksprache nötig ist. Das soll sich im Gesprächsverhalten widerspiegeln. | SO 4.2, AP 3.2 | F   | *offen*  |

### Trainingsgegenstand und Gesprächssimulation

| ID   | Anforderung                                                                                                                                                                                                            | Quelle                | Typ | Bezug      |
| :--- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------- | :-- | :--------- |
| R-05 | Nutzer wollen ein Gegenüber, mit dem sich realistische externe Kundengespräche üben lassen.                                                                                                                            | SO 4.4, AP 3.4        | F   | F-01       |
| R-06 | Das simulierte Gegenüber soll Gesprächsdynamik und emotionale Reaktionen abbilden, nicht nur fachliche Inhalte.                                                                                                        | SO 4.5                | F   | F-01, F-04 |
| R-07 | Kundentypen, die stark auf Kosten achten und Beratung ablehnen, sobald sie zusätzlich Geld kostet, sollen abbildbar sein.                                                                                              | SO 4.3, 4.5           | F   | F-04       |
| R-08 | Gesprächspartner vom Typ Geschäftsführer oder IT-Leiter mit Fokus auf Strategie und Budget sollen abbildbar sein.                                                                                                      | AP 3.5                | F   | F-04       |
| R-09 | Sowohl kurze, problemgetriebene Support-Fälle als auch längere beratende Projektgespräche sollen trainierbar sein.                                                                                                     | SO 4.1, 4.4, 4.6, 6.1 | F   | F-03, Q-06       |
| R-10 | Angebots- und Verkaufsgespräche, Preisdiskussionen sowie die Anforderungsdefinition sollen trainierbar sein.                                                                                                           | AP 3.4                | F   | F-03       |
| R-11 | Gesprächsverläufe, die sich über mehrere Termine erstrecken, sollen abbildbar sein.                                                                                                                                    | SO 4.4, 4.6           | F   | F-23       |
| R-12 | Nutzer wollen den Umgang mit spontanen Einwänden trainieren.                                                                                                                                                           | AP 2.1, 6             | F   | F-01       |
| R-13 | Follow-up-Gespräche folgen einem festen Phasenschema von Aufwärmen über Agenda, Kundennutzen, Vertrauensaufbau und Referenzen bis zu Preisverhandlung und Einwandbehandlung. Das Training soll sich daran orientieren. | AP 6                  | F   | F-42       |

### Erkennung von Sprech- und Kommunikationsverhalten

| ID   | Anforderung                                                                                                                                        | Quelle         | Typ | Bezug                  |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------------------- | :------------- | :-- | :--------------------- |
| R-14 | Nutzer wollen eigene blinde Flecken im Sprechverhalten erkennen, insbesondere bei Intonation, Sprechtempo, Lautstärke und undeutlicher Aussprache. | SO 1, 2.1, 6.1 | F   | F-35, F-36, F-37, F-38 |
| R-15 | Nutzer wollen erkennen, wenn sie einen Sachverhalt komplizierter erklären als nötig oder zu viele Informationen geben.                             | SO 3.1, 6.3    | F   | F-08                   |
| R-16 | Nutzer mit technischem Hintergrund wollen lernen, adressatengerecht statt stark technisch zu formulieren.                                          | AP 2.1         | F   | F-08, F-40             |
| R-17 | Nutzer wollen Missverständnisse erkennen, die im Gespräch entstehen, obwohl beide Seiten sich vermeintlich klar ausgedrückt haben.                 | SO 3.1, 3.2    | F   | F-08                   |
| R-18 | Nutzer wollen flüssiger und spontaner sprechen können, denn wie flüssig ein Gespräch verläuft, gilt als zentraler Erfolgsmaßstab.                       | AP 2.1, 5.2    | F   | F-51                |
| R-19 | Nutzer wollen verstehen, wie sie beim Gegenüber ankommen.                                                                                          | SO 4.10, 6.1   | F   | F-09, F-39             |
| R-49 | Nutzer wollen erkennen, ob sie im Gespräch nervös wirken. Als Indikatoren gelten Intonation und deutliche Aussprache.                              | SO-S 1         | F   | F-35, F-38, F-39       |
| R-50 | Der Anteil der Fragen im Gespräch soll ausgewiesen werden, da die fragende Seite das Gespräch führt.                                               | SO-S 1         | F   | F-53                   |

### Feedback und Auswertung

| ID   | Anforderung                                                                                                                                                   | Quelle         | Typ | Bezug      |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------- | :-- | :--------- |
| R-20 | Nutzer wollen nach einem Gespräch eine zusammenfassende Rückmeldung erhalten.                                                                                 | SO 6.3, AP 5.3 | F   | F-09       |
| R-21 | Die Rückmeldung soll qualitativ und differenziert ausfallen und sich nicht auf einen einzelnen Zahlenwert reduzieren. Quantitative Kennzahlen sind als Ergänzung erwünscht, nicht als Ersatz. | SO 6.2, 6.3, SO-S 1, AP-S 1 | Q   | Q-04, F-09, F-14 |
| R-22 | Nutzer wollen konkrete, anwendbare Verbesserungsvorschläge, die sich auf bestimmte Stellen im Gespräch beziehen.                                              | SO 6.3         | F   | F-10, F-47 |
| R-23 | Verbesserungsvorschläge sollen strukturiert sein. | AP 5.3         | F   | F-10       |
| R-24 | Nutzer wollen die Auswertung visuell im Stil eines Dashboards dargestellt bekommen.                                                                           | AP 5.3         | F   | F-53    |
| R-51 | Als Kennzahlen sind Redeanteil, Fragenanteil, Sprechtempo, Anzahl der Wörter, Reaktionszeit bis zur Antwort und Pausenzeiten belegt. Als ungeeignet wurde von keiner Seite eine Kennzahl benannt. Die Menge ist nicht abschließend und kann um weitere sinnvolle Kennzahlen erweitert werden. | SO-S 1, AP-S 1 | F   | F-53, F-24 |
| R-25 | Die Rückmeldung soll berücksichtigen, dass ein Gespräch von den Beteiligten unterschiedlich wahrgenommen wird.                                                | SO 6.3         | Q   | Q-01, F-09    |
| R-26 | Der Erfolg soll qualitativ gemessen werden: an Verständlichkeit, hilfreicher Gesprächsführung, Vertrauen, Kompetenzwirkung und der Flüssigkeit des Gesprächs. | SO 6.2, AP 5.2 | Q   | Q-01      |
| R-27 | Regelmäßiges Feedback ist Voraussetzung dafür, dass das Werkzeug angenommen wird.                                                                             | AP 3.10        | Q   | Q-05, F-13       |

### Reflexion und Lernprozess

| ID   | Anforderung                                                                                                                                      | Quelle         | Typ | Bezug      |
| :--- | :----------------------------------------------------------------------------------------------------------------------------------------------- | :------------- | :-- | :--------- |
| R-28 | Nutzer wollen Gespräche genauer reflektieren können, als es aus der bloßen Erinnerung möglich ist.                                               | SO 4.7         | F   | F-12       |
| R-29 | Das Training soll kontinuierlich über längere Zeiträume nutzbar sein, weil blinde Flecken sich erst mit der Zeit einschleifen.                   | SO 4.7, AP 3.7 | F   | F-13, F-48 |
| R-30 | Nutzer wollen die Entwicklung des eigenen Gesprächsverhaltens über mehrere Gespräche hinweg nachvollziehen.                                      | SO 4.7         | F   | F-13       |
| R-31 | Nutzer wollen das gemeinsame Verständnis nach einem Gespräch absichern, wie es bisher über eine zusammenfassende E-Mail an den Kunden geschieht. | SO 2.3, 3.3    | F   | F-09, F-54    |
| R-52 | Das Transkript soll unmittelbar nach dem Gespräch vollständig und in Textform vorliegen. Ein während des Gesprächs nur teilweise fertiges Transkript gilt als verwirrend.                         | SO-S 3, AP-S 3 | F   | F-12          |

### Bedienung und Akzeptanz

| ID   | Anforderung                                                                        | Quelle               | Typ | Bezug            |
| :--- | :--------------------------------------------------------------------------------- | :------------------- | :-- | :--------------- |
| R-32 | Der Nutzen des Trainers soll unmittelbar erkennbar und die Bedienung einfach sein. | SO 4.8, 4.10, AP 3.9 | Q   | Q-02           |
| R-33 | Eine unklare oder überladene Oberfläche soll die Nutzung nicht erschweren.         | SO 4.9, AP 3.9       | Q   | Q-02             |
| R-34 | Notwendige Einstellungen sollen klar sichtbar sein, Spezialoptionen zurücktreten.  | SO 4.9, 4.10         | Q   | Q-02, F-43            |
| R-53 | Die Sprache der Benutzeroberfläche soll sich leicht wechseln lassen. Deutsch und Englisch sind dafür zu Beginn ausreichend. Für Solox ist Mehrsprachigkeit nicht zwingend, da mit den Kunden auf Deutsch kommuniziert wird. | SO-S 2, AP-S 2       | F   | F-56             |
| R-54 | Die Beschriftungen der Oberfläche sollen vollständig und eindeutig sein, sodass die Bedeutung eines Bereichs ohne Suchen und Überlegen erkennbar ist. | SO-S 2               | Q   | Q-02             |
| R-55 | Wo sich die Bedeutung nicht bereits aus den Vorlauftexten der Eingabefelder ergibt, sollen Tooltips und Hinweise weiterführende Informationen bereitstellen. | SO-S 2               | F   | F-57             |

### Sprache, Geräte und Umfeld

| ID   | Anforderung                                                                                                                                                                                                   | Quelle              | Typ | Bezug      |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------------ | :-- | :--------- |
| R-35 | Das Training soll in der Sprache stattfinden, in der die Kundengespräche des jeweiligen Unternehmens geführt werden. Belegt sind Deutsch bei Solox sowie Englisch und teilweise Spanisch bei APPOLLO Systems. | SO 4.3, AP 3.3      | C   | C-01 |
| R-36 | Das Training soll am PC mit Headset durchführbar sein, analog zum Ablauf eines realen Telefonats.                                                                                                             | SO 5.1, 5.2         | C   | C-02       |
| R-37 | Das Training soll auch am Smartphone nutzbar sein, da mobile Telefonie in beiden Unternehmen im Einsatz ist.                                                                                                     | SO 5.2, AP 4.2      | C   | C-03       |
| R-38 | Eine Anbindung an die eingesetzte Telefonsoftware Starface ist denkbar.                                                                                                                                       | SO 5.1              | F   | F-29       |
| R-39 | Neben klassischen Telefonaten werden Konferenzwerkzeuge wie Teams, Zoom und GoToMeeting genutzt.                                                                                                              | SO 4.6, 5.1, AP 4.1 | F   | F-32       |

### Wissensbasis und Fachlichkeit

| ID   | Anforderung                                                                                                                                      | Quelle      | Typ | Bezug      |
| :--- | :----------------------------------------------------------------------------------------------------------------------------------------------- | :---------- | :-- | :--------- |
| R-40 | Das Training soll ohne kundenspezifisches Produkt- und Fachwissen durchführbar sein, da sich die Fachlichkeit je Kundenlandschaft unterscheidet. | SO 5.3, 5.4 | C   | C-05       |
| R-41 | Für einen ersten Prototyp soll keine vollständige Wissensbasis vorausgesetzt werden.                                                             | SO 5.4      | C   | C-05      |
| R-42 | Nutzer sollen bei Bedarf eigene Dokumente bereitstellen können, um den fachlichen Rahmen zu prägen. Ein solches Dokument soll darüber hinaus ein individuelles Szenario tragen können, um Gespräche mit stärkerem Unternehmensbezug zu üben. | SO 5.3, SO-S 5 | F   | F-26, F-45, F-58 |

### Nutzergesteuerte Szenarien

| ID   | Anforderung                                                                                                                                                                                                                     | Quelle         | Typ | Bezug   |
| :--- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------- | :-- | :------ |
| R-56 | Nutzer sollen die zu trainierende Gesprächssituation kurz beschreiben können, etwa Kunde, Projekt und Ausgangslage, woraus das System den passenden Gesprächspartner für die Sitzung ableitet. Das soll neben den vorgefertigten Szenarien stehen, nicht an deren Stelle. | SO-S 5, AP-S 5 | F   | *offen* |
| R-57 | Ein Beispiel soll zeigen, wie ein Szenario zu beschreiben ist, damit die Hürde gegenüber fertigen Szenarien nicht zu hoch ausfällt.                                                                                             | SO-S 5         | F   | *offen* |
| R-58 | Selbst erstellte Szenarien sollen nicht nur sitzungsbezogen, sondern mandantenbezogen gespeichert werden, sodass Kollegen ohne erneute Erfassung damit trainieren können.                                                        | SO-S 5         | F   | F-59    |
| R-59 | Ein hinterlegtes Szenario soll nachträglich bearbeitbar sein, um es nach- und feinjustieren zu können.                                                                                                                          | SO-S 5         | F   | *offen* |

### Erweiterung über die Simulation hinaus

| ID   | Anforderung                                                                                                                                                                                                                         | Quelle | Typ | Bezug   |
| :--- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----- | :-- | :------ |
| R-44 | Nutzer wollen echte Kundentelefonate mitlaufen lassen und auswerten, nicht nur simulierte Gespräche. Vom Gesprächspartner wird dafür Offenheit erwartet, auch weil Skripte und Protokolle für den Kunden einen Mehrwert darstellen. | AP 6   | F   | F-55 |

### Abgrenzungen

| ID   | Anforderung                                                                                                                                                   | Quelle         | Typ | Bezug      |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------- | :-- | :--------- |
| R-43 | Bestehende Gesprächsleitfäden und ihre Auswertung als Bewertungsgrundlage sind nicht Gegenstand des Trainings.                                                | AP 4.3, 4.4    | N   | *offen* |
| R-45 | Klassische vertriebliche Kennzahlen wie Abschlussquote oder Umsatz sollen nicht als Erfolgsmaßstab dienen.                                                    | SO 6.2, AP 5.2 | N   | *offen*       |
| R-46 | Ein stark vertriebslastiger Fokus passt nicht zu den Rollen bei Solox. Die Abgrenzung gilt unternehmensspezifisch und nicht produktweit, siehe Konflikt K-01. | SO 4.9         | N   | *offen* |
| R-47 | Fernwartung und Bildschirmfreigabe sind Teil realer Support-Gespräche, aber nicht Gegenstand des Trainings.                                                   | SO 4.4, 5.1    | N   | *offen*    |

### Zusammenarbeit

| ID   | Anforderung                                                                                                                            | Quelle       | Typ | Bezug    |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------- | :----------- | :-- | :------- |
| R-48 | Rückfragen an die fachlichen Ansprechpartner sollen gebündelt gestellt werden. Der bevorzugte Kanal unterscheidet sich je Unternehmen. | SO 7.1, AP 6 | C   | C-08 |

## Verteilung

| Typ               | Anzahl |
| :---------------- | :----- |
| Funktion (F)      | 38     |
| Qualitätsziel (Q) | 8      |
| Randbedingung (C) | 9      |
| Nicht-Ziel (N)    | 4      |
| **Gesamt**        | **59** |

Achtzehn Anforderungen sind unabhängig durch beide Unternehmen belegt.