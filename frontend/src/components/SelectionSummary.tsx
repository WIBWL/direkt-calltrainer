// These properties contain the labels shown in the selection summary.
interface SelectionSummaryProps {
  scenario: string;
  persona: string;
  language: string;
  voice: string;
}

export default function SelectionSummary({
  scenario,
  persona,
  language,
  voice,
}: SelectionSummaryProps) {
  // Keeping the entries in one array avoids repeating the same markup.
  const summaryItems = [
    { label: "Szenario", value: scenario },
    { label: "Gesprächspartner", value: persona },
    { label: "Sprache", value: language },
    { label: "Stimme", value: voice },
  ];

  return (
    <dl className="selection-summary">
      {summaryItems.map((item) => (
        <div className="selection-summary-item" key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
