<script lang="ts">
  import type { SignalRow } from "./api";
  import { formatChange, formatPrice, formatVolume } from "./format";

  export let signals: SignalRow[] = [];

  type SortKey =
    | "ticker"
    | "score"
    | "price"
    | "change_pct"
    | "volume"
    | "streak";
  let sortKey: SortKey = "score";
  let sortAsc = false;

  function sort(key: SortKey) {
    if (sortKey === key) {
      sortAsc = !sortAsc;
    } else {
      sortKey = key;
      sortAsc = key === "ticker";
    }
  }

  function arrow(key: SortKey): string {
    if (sortKey !== key) return "";
    return sortAsc ? " ↑" : " ↓";
  }

  function scoreColor(score: number): string {
    if (score >= 8) return "#10b981"; // mint
    if (score >= 6) return "#f59e0b"; // amber
    return "#ef4444"; // red
  }

  function tickerHue(t: string): number {
    let h = 0;
    for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) % 360;
    return h;
  }

  function formatSince(iso: string | null): string {
    if (!iso) return "";
    // iso is "YYYY-MM-DD" — render compactly
    return iso;
  }

  function groupAndSort(
    rows: SignalRow[],
    key: SortKey,
    asc: boolean,
  ): { name: string; items: SignalRow[] }[] {
    const m = new Map<string, SignalRow[]>();
    for (const s of rows) {
      const arr = m.get(s.screener) ?? [];
      arr.push(s);
      m.set(s.screener, arr);
    }
    const cmp = (a: SignalRow, b: SignalRow): number => {
      const av = a[key];
      const bv = b[key];
      if (av === null && bv === null) return 0;
      if (av === null) return 1;
      if (bv === null) return -1;
      const c = av < bv ? -1 : av > bv ? 1 : 0;
      return asc ? c : -c;
    };
    return Array.from(m.entries()).map(([name, items]) => ({
      name,
      items: [...items].sort(cmp),
    }));
  }

  // Reference sortKey / sortAsc directly here so Svelte tracks them as
  // dependencies — passing them as args to the helper guarantees the closure
  // sees the current values every time they change.
  $: groups = groupAndSort(signals, sortKey, sortAsc);
</script>

{#each groups as g}
  <section class="group">
    <header class="group-header">
      <h2>{g.name}</h2>
      <span class="group-count">{g.items.length} {g.items.length === 1 ? "signal" : "signals"}</span>
    </header>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th on:click={() => sort("ticker")}>Ticker{arrow("ticker")}</th>
            <th on:click={() => sort("score")} class="num">Pro Score{arrow("score")}</th>
            <th on:click={() => sort("price")} class="num">Price{arrow("price")}</th>
            <th on:click={() => sort("change_pct")} class="num">% Change{arrow("change_pct")}</th>
            <th on:click={() => sort("volume")} class="num">Volume{arrow("volume")}</th>
            <th on:click={() => sort("streak")} class="num">Streak{arrow("streak")}</th>
            <th class="static">Status</th>
            <th class="static">Analysis</th>
          </tr>
        </thead>
        <tbody>
          {#each g.items as s}
            <tr>
              <td>
                <a class="ticker-cell" href={`https://finviz.com/quote.ashx?t=${s.ticker}`} target="_blank" rel="noopener">
                  <span class="ticker-badge" style="background: hsl({tickerHue(s.ticker)}, 70%, 92%); color: hsl({tickerHue(s.ticker)}, 55%, 30%);">
                    {s.ticker.slice(0, 2)}
                  </span>
                  <span class="ticker-text">
                    <span class="ticker-sym">{s.ticker}</span>
                    {#if s.first_seen}
                      <span class="ticker-since">since {formatSince(s.first_seen)}</span>
                    {/if}
                  </span>
                </a>
              </td>
              <td class="num">
                <div class="score-cell">
                  <span class="score-num" style="color: {scoreColor(s.score)}">{s.score.toFixed(1)}</span>
                  <span class="score-bar"><span class="score-fill" style="width: {s.score * 10}%; background: {scoreColor(s.score)}"></span></span>
                </div>
              </td>
              <td class="num price">{formatPrice(s.price)}</td>
              <td class="num">
                {#if s.change_pct === null}
                  <span class="muted">—</span>
                {:else}
                  <span class={`pill ${s.change_pct >= 0 ? "pill-up" : "pill-down"}`}>{formatChange(s.change_pct)}</span>
                {/if}
              </td>
              <td class="num volume">{formatVolume(s.volume)}</td>
              <td class="num">
                {#if s.streak === null}
                  <span class="muted">—</span>
                {:else}
                  <span class={`pill ${s.streak >= 3 ? "pill-up" : "pill-neutral"}`}
                    >{s.streak}d{s.streak >= 5 ? " 🔥" : ""}</span
                  >
                {/if}
              </td>
              <td>
                {#if s.is_new_hit}
                  <span class="pill pill-new">NEW</span>
                {/if}
              </td>
              <td class="analysis">{s.analysis}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
{/each}

<style>
  .group {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    margin-bottom: 1.25rem;
    overflow: hidden;
  }

  .group-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--border-soft);
    background: var(--surface);
  }

  .group-header h2 {
    font-size: 15px;
    font-weight: 600;
    color: var(--text);
  }

  .group-count {
    color: var(--text-muted);
    font-size: 12px;
  }

  .table-wrap {
    overflow-x: auto;
  }

  :global(table th.num),
  :global(table td.num) {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .ticker-cell {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
    color: var(--text);
  }
  .ticker-cell:hover .ticker-sym {
    color: var(--primary);
  }

  .ticker-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  :global(thead th.static) {
    cursor: default;
  }
  :global(thead th.static:hover) {
    color: var(--text-muted);
  }

  .ticker-text {
    display: inline-flex;
    flex-direction: column;
    line-height: 1.25;
  }

  .ticker-sym {
    font-weight: 600;
    font-size: 13px;
    transition: color 0.15s;
  }

  .ticker-since {
    color: var(--text-faint);
    font-size: 11px;
    font-weight: 400;
  }

  .score-cell {
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    justify-content: flex-end;
  }
  .score-num {
    font-weight: 700;
    font-size: 13px;
    font-variant-numeric: tabular-nums;
    min-width: 26px;
    text-align: right;
  }
  .score-bar {
    display: inline-block;
    width: 64px;
    height: 4px;
    border-radius: 999px;
    background: var(--border-soft);
    overflow: hidden;
  }
  .score-fill {
    display: block;
    height: 100%;
    border-radius: 999px;
  }

  .price {
    font-weight: 600;
    font-size: 13px;
  }

  .volume {
    color: var(--text-muted);
    font-size: 13px;
  }

  .muted {
    color: var(--text-faint);
  }
</style>
