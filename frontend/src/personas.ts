import { apiFetch } from "./api";
import type { Persona, PersonaDetail } from "./protocol";

/** Read-only: Personas are curated (ADR 0058). */

export const listPersonas = () => apiFetch<Persona[]>("/api/personas");

export const getPersona = (id: string) => apiFetch<PersonaDetail>(`/api/personas/${id}`);
