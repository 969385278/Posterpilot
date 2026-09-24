export type State = Record<string, any>;
export type Snapshot = {values: State; next: string[]; step: number; checkpoint_id: string; interrupts: unknown[]};
export type Source = {id: string; path: string; symbol: string; start: number; end: number; code: string; sha256: string};
export type CaseRecord = {
  schemaVersion: number; id: string; capturedAt: string; commit: string; businessSourceModified: boolean;
  provenance: string; limitations: string[]; missing: State; collector: State; versions: State;
  initial: Snapshot; restored: Snapshot; history: Snapshot[]; final: Snapshot;
  decision: State; initialOutcome: State; outcome: State; providerCalls: State[]; renderCalls: State[];
  countsBeforeResume: State; backgroundEvidence: State; sources: Source[]; counterfactual: State;
  assets: {file: string; sha256: string; description: string}[];
};
export type Step = {
  id: string; title: string; module: string; inputLabel: string; outputLabel: string;
  symbols: string[]; highlights: Record<string, [number, number][]>;
  fields: string[]; what: string; why: string; cost: string; without: string; pseudo: string;
};
