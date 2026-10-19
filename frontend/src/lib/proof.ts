import { writable } from "svelte/store";

export type ProofKind = "fact" | "derived" | "unknown";

export type Proof = {
  value: string;
  how: string;
  kind: ProofKind;
  at?: string;
  factId?: number;
};

export const proof = writable<Proof | null>(null);
