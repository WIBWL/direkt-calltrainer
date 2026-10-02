import { apiFetch } from "./api";
import type { Persona, PersonaDetail } from "./protocol";

/** The Persona routes, read-only: Personas are curated, so there is nothing to
 *  write back (ADR 0058). */

export const listPersonas = () => apiFetch<Persona[]>("/api/personas");

/** The detail behind a Persona card's "i". */
export const getPersona = (id: string) => apiFetch<PersonaDetail>(`/api/personas/${id}`);
