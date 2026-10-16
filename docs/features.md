# Feature-Katalog

Funktionale Anforderungen. Code und Tests zitieren die IDs. *Herkunft*:

| Wert | Bedeutung |
|---|---|
| `R-xx` | aus einer Erhebung abgeleitet, siehe initial-requirements.md |
| `Q-xx` | dient einem Qualitätsziel, siehe arc42 Kapitel 10 |
| `C-xx` | folgt aus einer Randbedingung, siehe arc42 Kapitel 2 |
| `Systementwurf` | folgt aus dem Systementwurf, ohne Beleg aus einer Erhebung |

*Status* gibt den Umsetzungsstand im Code an:

| Wert | Bedeutung |
|---|---|
| `umgesetzt` | im Code vorhanden und nutzbar |
| `teilweise` | in Teilen vorhanden; der Zusatz nennt, was fehlt |
| `offen` | nicht umgesetzt |
| `bewusst nicht` | aus begründeter Entscheidung nicht gebaut; der Zusatz nennt die ADR |

## Gesprächssimulation und KI-Gegenpart

| ID | Feature | Prio | Herkunft | Status |
|---|---|---|---|---|
| F-01 | Live-Gesprächssimulation mit KI | MUST | R-05, R-06, R-12 | umgesetzt |
| F-03 | Szenario-Typen | MUST | R-03, R-09, R-10 | umgesetzt |
| F-04 | Kundenpersona-Bibliothek | MUST | R-06, R-07, R-08 | umgesetzt |
| F-23 | Mehrteilige Projektgespräche | COULD | R-11 | teilweise (nur über Folgeszenarien) |
| F-34 | Usergesteuertes Szenario | COULD | R-56, R-59 | umgesetzt |
| F-58 | Szenario aus hochgeladenem Dokument | SHOULD | R-42 | umgesetzt |
| F-60 | Folgeszenario aus dem Feedback | SHOULD | R-22, Systementwurf | umgesetzt |
| F-66 | Zufallsszenario | COULD | Systementwurf | umgesetzt |
| F-67 | Anruf annehmen statt starten | COULD | Systementwurf | umgesetzt |
| F-59 | Mandantenbezogene Szenario-Bibliothek | COULD | R-58 | umgesetzt |

## Sprach- und Kommunikationsanalyse

| ID | Feature | Prio | Herkunft | Status |
|---|---|---|---|---|
| F-35 | Analyse der Intonation | MUST | R-14, R-49 | umgesetzt |
| F-36 | Analyse des Sprechtempos | MUST | R-14 | umgesetzt |
| F-37 | Analyse der Lautstärke | MUST | R-14 | umgesetzt |
| F-38 | Analyse der Artikulation | MUST | R-14, R-49 | bewusst nicht (ADR 0084, 0111) |
| F-51 | Analyse der Sprechflüssigkeit | MUST | R-18 | umgesetzt |
| F-08 | Erkennung überlanger oder überkomplexer Erklärungen | MUST | R-15, R-16 R-17 | umgesetzt |
| F-40 | Analyse der sprachlichen Konkretheit | SHOULD | R-16 | offen |
| F-42 | Phasengerechte Sprache | COULD | R-13 | teilweise (Textblock im Wrap-up, keine Kennzahl) |
| F-24 | Analyse der Redeanteile | SHOULD | R-51, Systementwurf | umgesetzt |
| F-41 | Erkennung aktiven Zuhörens | SHOULD | Systementwurf | umgesetzt |
| F-39 | Kongruenz von Inhalt und Stimme | COULD | R-19, R-49 | offen |

## Feedback und Auswertung

| ID | Feature | Prio | Herkunft | Status |
|---|---|---|---|---|
| F-09 | Qualitatives Wrap-up | MUST | R-19, R-20, R-31 | umgesetzt |
| F-10 | Konkrete Verbesserungsvorschläge | MUST | R-22, R-23 | umgesetzt |
| F-53 | Auswertungs-Dashboard | SHOULD | R-24, R-50, R-51 | umgesetzt |
| F-47 | Verknüpfung von Feedback und Gesprächsstellen | COULD | R-22 | umgesetzt |
| F-14 | Score für das Gespräch | COULD | R-21 | bewusst nicht (ADR 0004, 0051) |
| F-54 | Gesprächszusammenfassung für den Gesprächspartner | COULD | R-31 | offen |

## Lernprozess und Reflexion

| ID | Feature | Prio | Herkunft | Status |
|---|---|---|---|---|
| F-12 | Aufzeichnung des Gesprächs | MUST | R-28, R-52 | umgesetzt |
| F-13 | Aufzeichnung des Fortschritts | SHOULD | R-27, R-29, R-30 | umgesetzt |
| F-68 | Gesprächsfeedback als PDF | COULD | F-12, Systementwurf | umgesetzt |
| F-48 | Trainingshistorie | COULD | R-29 | umgesetzt |
| F-61 | Rollentausch eines Gesprächs | COULD | R-25, R-28, R-01 | umgesetzt |
| F-62 | Persönliche Fokusziele | SHOULD | R-30, Systementwurf | umgesetzt |
| F-63 | Analyse des Gesprächseinstiegs | SHOULD | F-62 | umgesetzt |
| F-64 | Vorschlag für das nächste Gespräch | COULD | F-62 | umgesetzt |
| F-65 | Analyse des Gesprächsabschlusses | SHOULD | F-62 | umgesetzt |

## Bedienoberfläche

| ID | Feature | Prio | Herkunft | Status |
|---|---|---|---|---|
| F-43 | Setup-Übersicht | MUST | R-34 | umgesetzt |
| F-46 | Live-Call-Interface | MUST | Q-02, Systementwurf | umgesetzt |
| F-44 | Persona-Kartenansicht | SHOULD | Q-02 | umgesetzt |
| F-45 | Wissensbasis-Upload-Oberfläche | SHOULD | R-42 | umgesetzt |
| F-56 | Sprachumschaltung der Oberfläche | SHOULD | R-53 | offen |
| F-57 | Kontexthilfen in der Oberfläche | COULD | R-55 | teilweise (Info-Panels, keine Hilfen an Eingabefeldern) |

## Konto und Zugriff

| ID | Feature | Prio | Herkunft | Status |
|---|---|---|---|---|
| F-31 | Accountsystem | MUST | C-04 | umgesetzt |
| F-50 | Login und Authentifizierung | MUST | C-04 | umgesetzt |
| F-49 | Datenschutzhinweis beim Start | MUST | C-04 | umgesetzt |

## Integration und Wissensanbindung

| ID | Feature | Prio | Herkunft | Status |
|---|---|---|---|---|
| F-26 | Kundenspezifische Wissensbasis | SHOULD | R-42 | teilweise (Dokument nur je Szenario, ADR 0005) |
| F-29 | Anbindung an die Telefonsoftware Starface | COULD | R-38 | offen |
| F-55 | Auswertung realer Kundengespräche | COULD | R-44 | offen |

## Multimodale Erweiterung

| ID | Feature | Prio | Herkunft | Status |
|---|---|---|---|---|
| F-32 | Videobasierte Verarbeitung | COULD | R-39 | offen |
| F-33 | Analyse der visuellen nonverbalen Kommunikation | COULD | Systementwurf | offen |
