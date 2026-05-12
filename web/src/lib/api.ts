export interface SignalRow {
  ticker: string;
  screener: string;
  score: number;
  analysis: string;
  is_new_hit: boolean;
  price: number | null;
  change_pct: number | null;
  volume: number | null;
}

export interface RunSummary {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  n_signals: number;
  n_new_hits: number;
}

export interface RunDetail {
  run: RunSummary;
  signals: SignalRow[];
}

export interface Manifest {
  generated_at: string;
  latest_run_id: number | null;
  score_threshold: number;
}

const DEV = import.meta.env.DEV;
const API_BASE = DEV ? "http://localhost:8000/api" : null;

async function fetchJson<T>(path: string): Promise<T> {
  const url = API_BASE ? `${API_BASE}${path}` : `./data${path}.json`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText} — ${url}`);
  return resp.json() as Promise<T>;
}

export const fetchLatest = (): Promise<RunDetail> => fetchJson("/latest");
export const fetchRuns = (): Promise<RunSummary[]> => fetchJson("/runs");
export const fetchRun = (id: number): Promise<RunDetail> => fetchJson(`/runs/${id}`);
export const fetchManifest = (): Promise<Manifest> =>
  fetch("./data/manifest.json").then((r) => r.json() as Promise<Manifest>);
