# Feature-Katalog

Funktionale Anforderungen. Code und Tests zitieren die IDs. *Herkunft*:

| Wert | Bedeutung |
|---|---|
| `R-xx` | aus einer Erhebung abgeleitet, siehe initial-requirements.md |
| `Q-xx` | dient einem Qualitätsziel, siehe arc42 Kapitel 10 |
| `C-xx` | folgt aus einer Randbedingung, siehe arc42 Kapitel 2 |
| `Systementwurf` | folgt aus dem Systementwurf, ohne Beleg aus einer Erhebung |

## Gesprächssimulation und KI-Gegenpart

| ID | Feature | Prio | Herkunft |
|---|---|---|---|
| F-01 | Live-Gesprächssimulation mit KI | MUST | R-05, R-06, R-12 |
| F-03 | Szenario-Typen | MUST | R-03, R-09, R-10 |
| F-04 | Kundenpersona-Bibliothek | MUST | R-06, R-07, R-08 |
| F-23 | Mehrteilige Projektgespräche | COULD | R-11 |
| F-34 | Usergesteuertes Szenario | COULD | Systementwurf |
| F-58 | Szenario aus hochgeladenem Dokument | SHOULD | R-42 |
| F-60 | Folgeszenario aus dem Feedback | SHOULD | R-22, Systementwurf |
| F-66 | Zufallsszenario | COULD | Systementwurf |
| F-67 | Anruf annehmen statt starten | COULD | Systementwurf |
| F-59 | Mandantenbezogene Szenario-Bibliothek | COULD | R-58 |

## Sprach- und Kommunikationsanalyse

| ID | Feature | Prio | Herkunft |
|---|---|---|---|
| F-35 | Analyse der Intonation | MUST | R-14, R-49 |
| F-36 | Analyse des Sprechtempos | MUST | R-14 |
| F-37 | Analyse der Lautstärke | MUST | R-14 |
| F-38 | Analyse der Artikulation | MUST | R-14, R-49 |
| F-51 | Analyse der Sprechflüssigkeit | MUST | R-18 |
| F-08 | Erkennung überlanger oder überkomplexer Erklärungen | MUST | R-15, R-16 R-17 |
| F-40 | Analyse der sprachlichen Konkretheit | SHOULD | R-16 |
| F-42 | Phasengerechte Sprache | COULD | R-13 |
| F-24 | Analyse der Redeanteile | SHOULD | R-51, Systementwurf |
| F-41 | Erkennung aktiven Zuhörens | SHOULD | Systementwurf |
| F-39 | Kongruenz von Inhalt und Stimme | COULD | R-19, R-49 |

## Feedback und Auswertung

| ID | Feature | Prio | Herkunft |
|---|---|---|---|
| F-09 | Qualitatives Wrap-up | MUST | R-19, R-20, R-31 |
| F-10 | Konkrete Verbesserungsvorschläge | MUST | R-22, R-23 |
| F-53 | Auswertungs-Dashboard | SHOULD | R-24, R-50, R-51 |
| F-47 | Verknüpfung von Feedback und Gesprächsstellen | COULD | R-22 |
| F-14 | Score für das Gespräch | COULD | R-21 |
| F-54 | Gesprächszusammenfassung für den Gesprächspartner | COULD | R-31 |

## Lernprozess und Reflexion

| ID | Feature | Prio | Herkunft |
|---|---|---|---|
| F-12 | Aufzeichnung des Gesprächs | MUST | R-28, R-52 |
| F-13 | Aufzeichnung des Fortschritts | SHOULD | R-27, R-29, R-30 |
| F-68 | Gesprächsfeedback als PDF | COULD | F-12, Systementwurf |
| F-48 | Trainingshistorie | COULD | R-29 |
| F-61 | Rollentausch eines Gesprächs | COULD | R-25, R-28, R-01 |
| F-62 | Persönliche Fokusziele | SHOULD | R-30, Systementwurf |
| F-63 | Analyse des Gesprächseinstiegs | SHOULD | F-62 |
| F-64 | Vorschlag für das nächste Gespräch | COULD | F-62 |
| F-65 | Analyse des Gesprächsabschlusses | SHOULD | F-62 |

## Bedienoberfläche

| ID | Feature | Prio | Herkunft |
|---|---|---|---|
| F-43 | Setup-Übersicht | MUST | R-34 |
| F-46 | Live-Call-Interface | MUST | Q-02, Systementwurf |
| F-44 | Persona-Kartenansicht | SHOULD | Q-02 |
| F-45 | Wissensbasis-Upload-Oberfläche | SHOULD | R-42 |
| F-56 | Sprachumschaltung der Oberfläche | SHOULD | R-53 |
| F-57 | Kontexthilfen in der Oberfläche | COULD | R-55 |

## Konto und Zugriff

| ID | Feature | Prio | Herkunft |
|---|---|---|---|
| F-31 | Accountsystem | MUST | C-04 |
| F-50 | Login und Authentifizierung | MUST | C-04 |
| F-49 | Datenschutzhinweis beim Start | MUST | C-04 |

## Integration und Wissensanbindung

| ID | Feature | Prio | Herkunft |
|---|---|---|---|
| F-26 | Kundenspezifische Wissensbasis | SHOULD | R-42 |
| F-29 | Anbindung an die Telefonsoftware Starface | COULD | R-38 |
| F-55 | Auswertung realer Kundengespräche | COULD | R-44 |

## Multimodale Erweiterung

| ID | Feature | Prio | Herkunft |
|---|---|---|---|
| F-32 | Videobasierte Verarbeitung | COULD | R-39 |
| F-33 | Analyse der visuellen nonverbalen Kommunikation | COULD | Systementwurf |
