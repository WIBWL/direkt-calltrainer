import cardUrl from "../assets/reverse-card.png";

/**
 * The card that spins across the screen when the roles are swapped (F-61).
 *
 * Built from the reverse card of the card game it alludes to, recoloured into
 * the DiReKT palette: face `--color-blue-600`, the arrows' shadow
 * `--color-navy-900`, the printed card's white border put back around it. The
 * shape and the symbol are still that game's — whoever takes this past the
 * pilot should know that rather than discover it.
 *
 * Blue-600 and not a navy because the card is shown against the transition's
 * navy scrim, where a navy card is a white outline around nothing.
 *
 * Prepared rather than dropped in (`scratchpad/make_card.py`): cropped,
 * recoloured as a blend of three anchors so the antialiased edges survive, cut
 * to its own rounded corners with an alpha channel, and stored as a 64-colour
 * PNG at twice the largest size it is ever shown at — for flat colours a tenth
 * the size of full RGBA with no visible loss.
 */
export default function ReverseCard() {
  return <img className="reverse-card" src={cardUrl} alt="" />;
}
