/** SVG, not an emoji, which Windows renders as letters. It stands for the language. Decorative. */

/** One 3:2 box, so a row of flags lines up. */
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
  const stripe = 40 / 13;
  return (
    <svg {...BOX} aria-hidden="true">
      <rect width="60" height="40" fill="#ffffff" />
      {[0, 2, 4, 6, 8, 10, 12].map((i) => (
        <rect key={i} y={i * stripe} width="60" height={stripe} fill="#b22234" />
      ))}
      <rect width="24" height={7 * stripe} fill="#3c3b6e" />
      {/* Dots: a star under a pixel across is a smudge. */}
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
  // An unknown code shows no flag rather than a wrong one.
  if (code === "de") return <GermanFlag />;
  if (code === "en") return <UnitedStatesFlag />;
  return null;
}
