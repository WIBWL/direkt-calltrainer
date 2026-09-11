/**
 * The flag beside a Persona's name: which language this one speaks.
 *
 * Drawn as SVG rather than written as a flag emoji, because Windows ships no
 * glyphs for those — Chrome and Edge there render 🇩🇪 as the letters "DE",
 * which is precisely the audience this app is built for.
 *
 * The flag says the *language*, not a country: English is shown as the US flag
 * because that is what was asked for, and because a Persona's language is a
 * voice and an accent rather than a nationality. A further language means one
 * more case here and one more `LanguagePack` on the server.
 *
 * Decorative on purpose: every place this appears already carries the language
 * as text ("Deutsch"), so an alt text would have a screen reader say the same
 * thing twice.
 */

/** A uniform 3:2 box for every flag. Neither flag's true proportions, but a row
 * of them lines up, which matters more here than either does. */
const BOX = { viewBox: "0 0 60 40", className: "language-flag" } as const;

function GermanFlag() {
  return (
    <svg {...BOX} aria-hidden="true">
      <rect width="60" height="13.34" fill="#000000" />
      <rect y="13.33" width="60" height="13.34" fill="#dd0000" />
      <rect y="26.66" width="60" height="13.34" fill="#ffce00" />
    </svg>
  );
}

function UnitedStatesFlag() {
  // Thirteen stripes and not a legible-at-16px seven: at this size they read as
  // a striped flag either way, and the wrong number is the kind of detail
  // someone notices exactly once and never unsees.
  const stripe = 40 / 13;
  return (
    <svg {...BOX} aria-hidden="true">
      <rect width="60" height="40" fill="#ffffff" />
      {[0, 2, 4, 6, 8, 10, 12].map((i) => (
        <rect key={i} y={i * stripe} width="60" height={stripe} fill="#b22234" />
      ))}
      <rect width="24" height={7 * stripe} fill="#3c3b6e" />
      {/* The stars as dots: at the size this is shown they are under a pixel
          across, and a five-pointed star drawn there is a smudge with corners
          rather than a star. */}
      {Array.from({ length: 5 }, (_, row) =>
        Array.from({ length: row % 2 === 0 ? 5 : 4 }, (_, col) => (
          <circle
            key={`${row}-${col}`}
            cx={(24 * (col + 0.5 + (row % 2 === 0 ? 0 : 0.5))) / 5}
            cy={(7 * stripe * (row + 0.5)) / 5}
            r="1.3"
            fill="#ffffff"
          />
        )),
      )}
    </svg>
  );
}

export default function LanguageFlag({ code }: { code: string }) {
  // Only the two languages there are Personas for. An unknown code shows no
  // flag rather than a wrong one — the name beside it still says the language.
  if (code === "de") return <GermanFlag />;
  if (code === "en") return <UnitedStatesFlag />;
  return null;
}
