/**
 * Blocks D and E of the dashboard concept, as a labelled preview.
 *
 * These two need something that does not exist yet: the wrap-up writes its
 * strengths and improvement points as free text with no link to a goal
 * (`feedback_point` carries a Turn reference and nothing else), so there is no
 * way to count what recurs across a user's trainings. The concept's stage 2
 * adds that tag at the point the wrap-up is written; until then this area can
 * be laid out but not filled.
 *
 * Shown rather than left out, because the layout is what is under discussion
 * and an empty stretch of page discusses nothing. Shown as an example rather
 * than as data, emphatically: inventing a plausible weakness and putting it in
 * front of someone under their own name would be the single worst thing this
 * screen could do. The frame says "Beispiel", the entries are visibly
 * placeholders, and the button does not act.
 */
export default function ProgressPreview() {
  return (
    <section className="progress-section" aria-labelledby="preview-title">
      <div className="progress-section-head">
        <h2 id="preview-title">Was in Ihren Auswertungen wiederkehrt</h2>
        <span className="chip chip-neutral">Beispiel</span>
      </div>

      <div className="card progress-preview">
        <p className="progress-preview-note">
          So ist dieser Bereich geplant. Die Einträge unten sind erfunden und sagen nichts über
          Sie aus. Gefüllt wird er, sobald die Auswertung jedem Punkt eines ihrer Fokusziele
          zuordnet. Dann steht hier, was über mehrere Gespräche hinweg wiederholt genannt wurde,
          und zwar als Häufigkeit einer Aussage, nicht als Bewertung.
        </p>

        <div className="progress-preview-columns" aria-hidden="true">
          <div>
            <h3 className="progress-preview-heading">Häufig als Stärke genannt</h3>
            <ul className="progress-preview-list">
              <li>
                Klare Struktur <span className="progress-preview-count">5 von 8</span>
              </li>
              <li>
                Ruhiger Ton <span className="progress-preview-count">4 von 8</span>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="progress-preview-heading">Häufig als Verbesserung genannt</h3>
            <ul className="progress-preview-list">
              <li>
                Abschluss bleibt offen <span className="progress-preview-count">4 von 8</span>
              </li>
              <li>
                Zu früh beim Preis <span className="progress-preview-count">3 von 8</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="progress-preview-practice" aria-hidden="true">
          <div>
            <p className="progress-preview-heading">Gezielt üben</p>
            <p className="progress-preview-reason">
              Szenario „Abschluss nach Übergabe“ mit Thomas Brandt, weil der Abschluss zuletzt
              dreimal genannt wurde.
            </p>
          </div>
          <button type="button" className="consent-button consent-button-secondary" disabled>
            Training starten
          </button>
        </div>
      </div>
    </section>
  );
}
