# Merge-Protokoll: `dev` nach `main` (2026-10-04)

Dieses Protokoll begleitet den Branch `merge/dev-into-main`. Es hält fest, wie die Arbeit auf `dev` in den umgebauten Stand von `main` übernommen wurde, wo dabei Code von `main` angefasst werden musste und was vor dem Übernehmen nach `main` noch zu prüfen ist.

## Ausgangslage

| | Commit | Stand |
|---|---|---|
| `main` | `cff9a16` „Change client and separate audience" | 12 Commits seit dem gemeinsamen Ursprung: Aufteilung in `shared`/`backend`/`worker` (ADR 0108), Einstellungen über `shared/env.py` (ADR 0106), API auf eigenem Host hinter CORS (ADR 0107), Logs nur auf stdout (ADR 0105), Rolle und Kontingente (ADR 0109), Keycloak Organizations, Entfernen personenbezogener Daten |
| `dev` | `3381453` „Ask the user to greet the caller when picking up" | 38 Commits seit dem gemeinsamen Ursprung: Features, Fixes, arc42-Überarbeitung |
| gemeinsamer Ursprung | `ff7c552` „Replace caddy files" | |

**Grundsatz:** `main` hat Vorrang. Struktur, Infrastruktur und Entscheidungen von `main` bleiben, wie sie sind. Die Funktionen von `dev` wurden in diese Struktur eingepasst. Wo das ohne Eingriff in Code von `main` nicht ging, steht der Eingriff unten unter „Eingriffe in Code von `main`“.

`main` und `dev` selbst wurden nicht verändert.

## Ablauf

1. **Hilfscommit auf `dev`, ADR-Nummern (`43c4288`).** `main` und `dev` hatten die Nummern 0105 bis 0109 unabhängig voneinander vergeben. Da alle Verweise auf diese Nummern, die `dev` geschrieben hat, eindeutig `dev`s ADRs meinen, wurde vor dem Merge auf einem Hilfsbranch von `dev` umnummeriert. Danach war jeder Treffer im Merge eindeutig. Ausgenommen war `docs/arc42.md`: Dort verwies `dev` bereits auf die ADRs 0105 bis 0108 von `main` und nur mit 0110 auf einen eigenen.
2. **Merge** dieses Hilfsbranches in einen Branch von `main` (`git merge --no-ff`, Umbenennungserkennung an).
3. **Konflikte aufgelöst** und die neuen Dateien von `dev` in die Paketstruktur von `main` gelegt (unten im Einzelnen).
4. **Prüfungen**: Tests, Linter, Build, Abgleich auf personenbezogene Daten (unten).

### Neue ADR-Nummern

| ADR auf `dev` | neue Nummer | Titel |
|---|---|---|
| 0105 | **0111** | „Deutliche Artikulation" Is Retired from the Focus Catalogue |
| 0106 | **0112** | The Dashboard Reads One Client-Side Load and Adds No Endpoint |
| 0107 | **0113** | The Progress Report Is a Second Document on the Same Page Frame |
| 0108 | **0114** | The VAD's Padding Is Not Speech |
| 0109 | **0115** | A Call's Figures Are Placed Against the User's Own Usual Range |
| 0110 | 0110 (unverändert) | The User Picks Up First; Only a Reverse Is Answered by the Persona |

0110 behält seine Nummer, weil `dev`s arc42 sie schon neben den Nummern von `main` benutzt hat. Umgestellt wurden Dateinamen, Überschriften, `mkdocs.yml` und alle Verweise in Code, Tests und Docs, insgesamt 63 Stellen in 26 Dateien. Die ADR-Tabelle in arc42 Kapitel 9 führt jetzt auch 0109 (von `main`, dort bisher nicht eingetragen) und 0111 bis 0115.

## Konflikte und ihre Auflösung

| Datei | Konflikt | Auflösung |
|---|---|---|
| `frontend/Dockerfile`, `frontend/spa.conf.template` | `main` hat beide gelöscht, `dev` hat beide geändert | gelöscht wie auf `main`. Der `.mjs`-Fix von `dev` steckt schon in `frontend/docker/default.conf`. Den `npm test`-Schritt von `dev` trägt jetzt das Root-`Dockerfile` (siehe Eingriffe) |
| `backend/api/session_ws.py` | Docstring von `_run_session`: Zeitlimit (`main`) gegen Abnehmen (`dev`) | beide Teile übernommen |
| `backend/documents.py` | Docstring: Child-Process und `MAX_DOCUMENTS` (`main`) gegen „kein Thinking-Modus“ (`dev`) | beide Teile übernommen |
| `backend/followups.py` | Importe | `shared.clients.llm` (`main`) plus `FIELD_LIMITS` (`dev`) |
| `shared/feedback/metrics.py` | Importe | Pfade von `main` plus `Reaction` (`dev`) |
| `backend/tests/test_websocket_protocol.py` | Docstring, Importe, zwei Testblöcke | beide Testblöcke übernommen. Die Tests von `dev` rufen `_run_session` jetzt mit dem `deadline`-Argument von `main` auf |
| `backend/tests/test_session_pipeline.py` | Importe | Pfade von `main` (`backend.session.events`, `shared.turn`) plus `attach_measurements` (`dev`) |
| `backend/tests/test_scenario_documents.py` | Docstring | beide Teile übernommen |
| `docs/adr/0103-…` | Client-Name im Statusvermerk | `calltrainer-frontend` (`main`), dazu die Ergänzung von `dev` vom 2026-10-02 |
| `mkdocs.yml` | ADR-Navigation | 0105 bis 0109 (`main`), dann 0110 bis 0115 (`dev`) |
| `CLAUDE.md` | Fallstricke und Build/Run | Text von `main` vollständig. Von `dev` nur der Fallstrick „The User picks up first“ und der Eintrag zu `backfill_voiced_span` (in der Aufrufform von `main`). Der alte Build/Run-Teil von `dev` (Compose, `docker-bake.hcl`, `.env`-Pfade) wurde verworfen |
| `docs/codebase-notes.md` | zwei Sätze in Absätzen von je ~137 KB | Drei-Wege-Merge auf Satzebene. Bei der Briefing-Anzeige gilt die Beschreibung von `dev` mit dem Testpfad von `main`. Bei Mandanten und Auth gilt der Text von `main`, ergänzt um den Satz von `dev` zu `persona.hard` |
| `docs/arc42.md` | sieben Blöcke | Die Überarbeitung von `dev` war schon an `main` angeglichen (und anonymisiert). Wo `main` nur alten Text anonymisiert hatte, den `dev` ersetzt hat, gilt `dev`. Zusammengeführt wurden die Tabellenzeile „Authentifizierung“ (Rolle `calltrainer-user` aus ADR 0109 **und** Organizations) und der Absatz zu `AuthGate` (Hinweis auf das 403 aus ADR 0109 bleibt) |

### Neue Dateien von `dev` in der Struktur von `main`

| auf `dev` | im Merge |
|---|---|
| `backend/db/migrations/versions/c2e8a41f7d65_persona_hard_flag.py` | `shared/db/migrations/versions/` |
| `scripts/backfill_voiced_span.py` | `backend/scripts/backfill_voiced_span.py`, Aufruf `python -m backend.scripts.backfill_voiced_span` |
| `tests/test_backfill_voiced_span.py`, `tests/test_pickup_prompt.py` | `backend/tests/` |
| `backend/session/pickup.py` | an Ort und Stelle, Import `shared.turn.Turn` statt `backend.session.models` |

Alle Importe in diesen Dateien zeigen auf die Pfade von `main`. Die Migrationskette hat genau einen Kopf (`c2e8a41f7d65`). `main` hatte keine eigene Migration hinzugefügt.

## Eingriffe in Code von `main`

Diese Stellen ändern Code oder Dateien, die auf `main` so nicht standen, über das bloße Einfügen von `dev`s Inhalten hinaus. Sie sind die Punkte, die beim Review besonders angesehen werden sollten.

1. **`shared/feedback/segments.py` (neu) und `worker/segments.py` (gekürzt).**
   *Warum:* Das Backfill-Skript von `dev` braucht `measure_segments`. Auf `main` lag die Funktion in `worker/segments.py`, und Backend-Skripte dürfen den Worker nicht importieren (`test_module_dependencies.py`). Beim Aufteilen war der Generator ihr einziger Nutzer. Erst `dev`s Skript ist ein zweiter, und den gab es auf `main` noch nicht.
   *Was:* `measure_segments`, `_pressure_marked`, `SEGMENT_METRIC_KEYS` und `MIN_UTTERANCES` wurden unverändert nach `shared/feedback/segments.py` verschoben. Das entspricht der Einteilung aus ADR 0108 („shared — … the measuring code“; „backend — … the scripts“). `worker/segments.py` behält `store`/`_write` und importiert das Messen. `worker/tests/test_pressure_segments.py` holt `SEGMENT_METRIC_KEYS` von dort. Die Logik ist unverändert.
2. **`backend/api/session_ws.py`, `_run_session`.**
   *Warum:* Erst `main`s Zeitlimit (ADR 0109) und `dev`s „Hallo?“-Zweig (ADR 0110) zusammen bringen die Funktion über flake8s `max-complexity` von 10 (gemessen 12).
   *Was:* Das „Hallo?“ wird wie ein Turn behandelt und läuft durch die vorhandene Ergebnisbehandlung, statt eine eigene zu haben. `main`s zwei Prüfungen der Turn-Audiodaten (fehlender Binärframe, `MAX_TURN_AUDIO_BYTES`) stehen wortgleich in der neuen Hilfsfunktion `_turn_audio`. Das Verhalten ist unverändert, die Tests beider Seiten laufen grün.
3. **Root-`Dockerfile`:** `RUN npm test` vor `RUN npm run build` in `frontend-build`. Damit ist `dev`s Commit `edb2472` („Run the frontend tests in the image build“) übernommen, der auf `main` an das gelöschte `frontend/Dockerfile` gebunden war. Der Schritt braucht keine Einstellungen. Wer ihn nicht will, streicht die eine Zeile mit ihrem Kommentar.
4. **`CLAUDE.md`, `docs/arc42.md`:** `segments.py` ist jetzt bei `shared/feedback/` aufgeführt, und der Worker-Eintrag sagt „speichert“. In der ADR-Tabelle von arc42 gibt es neue Zeilen für 0109 und 0111 bis 0115, und der Satz zu leeren *Betrifft*-Zellen nennt jetzt „0104 bis 0109“.

## Prüfungen

| Prüfung | Ergebnis |
|---|---|
| `pytest` (alle drei Suiten, Persistenztests gegen Wegwerf-Datenbanken auf einem lokalen Postgres) | siehe unten |
| `flake8` | sauber |
| `pylint backend/ shared/ worker/` | 10.00/10 |
| `npm run lint` | sauber |
| `npm test` (Vitest) | 20 Dateien, 251 Tests bestanden |
| `npm run build` | erfolgreich |
| Personenbezogene Daten | Alle Namen, Firmen und Dev-Nutzer, die `main` in `50e4fd4` entfernt hat (Firmen, Ansprechpartner, `niklas`/`mathias`/`eberhard`, `solox`/`appollo`), kommen im Merge-Ergebnis nicht vor |
| Frontend-Aufrufe | Neuer Code von `dev` geht durchgängig über `apiFetch`/`WS_URL`, also auch mit dem eigenen API-Host aus ADR 0107 |

**pytest:** 1340 bestanden, 1 fehlgeschlagen, 0 übersprungen. Der eine Fehlschlag ist `backend/tests/test_request_limits.py::test_the_socket_frame_ceiling_sits_above_one_turn`. Er tritt nur unter Windows auf (siehe nächster Abschnitt), und weder der Test noch `gunicorn_worker.py` noch `limits.py` unterscheiden sich von `main`.

Getestet wurde unter Windows mit Python 3.12 (uv-verwaltet) gegen das Lockfile (`uv sync --locked`).

## Vor dem Übernehmen nach `main` und beim Deployment

- **`test_request_limits.py::test_the_socket_frame_ceiling_sits_above_one_turn` scheitert unter Windows** (`fcntl` fehlt, gunicorn ist Unix-only). Das ist auf `main` genauso und hat mit dem Merge nichts zu tun. Unter Linux und macOS sollte der Test laufen.
- **Migration `c2e8a41f7d65` (`persona.hard`)** läuft beim Start des Backends automatisch. Vorher wie üblich `pg_dump`.
- **Einmal nach dem Deployment:** `python -m backend.scripts.backfill_voiced_span` (Trockenlauf), dann mit `--apply`. Ohne diesen Schritt mischt die Fortschrittsansicht bei vor ADR 0114 gespeicherten Sessions alte und neue Definition von Redeanteil, Redefluss und Reaktionszeit. Das Skript ist idempotent.
- **Datenschutzerklärung:** `dev` verweist `/datenschutz` auf <https://efre-direkt.de/privacy/>. Was diese Seite vor echten Nutzern noch beschreiben muss, steht unter „Legal“ in `docs/deployment.md` (blockierend).
- ADR 0115 ist angenommen, aber noch nicht umgesetzt.
- Die beiden neuen Testdateien von `dev` (`test_pickup_prompt.py`, `test_backfill_voiced_span.py`) stehen noch nicht in der Matrix von `docs/testing.md`. Auch auf `dev` fehlten sie dort.
