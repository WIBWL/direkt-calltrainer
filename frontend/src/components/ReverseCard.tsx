import cardUrl from "../assets/reverse-card.png";

/**
 * The card that spins across the screen when the roles are swapped (F-61).
 *
 * Built from the reverse card of the card game it alludes to, recoloured into
 * the DiReKT palette at the project owner's decision: the face is
 * `--color-blue-600`, the arrows' shadow `--color-navy-900`, and the white
 * border a printed card has is put back around it. The shape and the symbol
 * are still that game's; the colours are not. Whoever takes this past the
 * pilot should know where it comes from rather than discover it.
 *
 * Blue-600 and not one of the navies because this card is shown against the
 * transition's navy scrim, where a navy card is a white outline around
 * nothing.
 *
 * Prepared rather than dropped in (`scratchpad/make_card.py` built it): cropped
 * to the card, recoloured as a blend of three anchors so the artwork's
 * antialiased edges survive, cut to its own rounded corners with an alpha
 * channel, and stored as a 64-colour PNG — for flat colours a tenth of the
 * size of full RGBA and no visible loss — at twice the largest size the
 * animation ever shows it at.
 */
export default function ReverseCard() {
  return <img className="reverse-card" src={cardUrl} alt="" />;
}
