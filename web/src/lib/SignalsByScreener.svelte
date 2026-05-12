<script lang="ts">
  import type { SignalRow } from "./api";
  import { formatChange, formatPrice, formatVolume } from "./format";

  export let signals: SignalRow[] = [];

  type SortKey = "ticker" | "score" | "price" | "change_pct" | "volume";
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
    return sortAsc ? " ▲" : " ▼";
  }

  function cmp(a: SignalRow, b: SignalRow): number {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    const c = av < bv ? -1 : av > bv ? 1 : 0;
    return sortAsc ? c : -c;
  }

  // Preserve insertion order of screeners as they appear in `signals`.
  $: groups = (() => {
    const m = new Map<string, SignalRow[]>();
    for (const s of signals) {
      const arr = m.get(s.screener) ?? [];
      arr.push(s);
      m.set(s.screener, arr);
    }
    return Array.from(m.entries()).map(([name, items]) => ({
      name,
      items: [...items].sort(cmp),
    }));
  })();
</script>

{#each groups as g}
  <h2 class="group-heading">{g.name} <span class="group-count">({g.items.length})</span></h2>
  <table>
    <thead>
      <tr>
        <th on:click={() => sort("ticker")}>Ticker{arrow("ticker")}</th>
        <th on:click={() => sort("score")}>Score{arrow("score")}</th>
        <th on:click={() => sort("price")}>Price{arrow("price")}</th>
        <th on:click={() => sort("change_pct")}>Chg%{arrow("change_pct")}</th>
        <th on:click={() => sort("volume")}>Volume{arrow("volume")}</th>
        <th>New</th>
        <th>Analysis</th>
      </tr>
    </thead>
    <tbody>
      {#each g.items as s}
        <tr class={s.is_new_hit ? "new-hit" : ""}>
          <td>
            <a href={`https://finviz.com/quote.ashx?t=${s.ticker}`} target="_blank">{s.ticker}</a>
          </td>
          <td class={`score score-${s.score}`}>{s.score}</td>
          <td>{formatPrice(s.price)}</td>
          <td class={s.change_pct === null ? "" : s.change_pct >= 0 ? "up" : "down"}>
            {formatChange(s.change_pct)}
          </td>
          <td>{formatVolume(s.volume)}</td>
          <td>{s.is_new_hit ? "★" : ""}</td>
          <td class="analysis">{s.analysis}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/each}

<style>
  .group-heading {
    margin-top: 1.5rem;
    font-size: 14px;
    font-weight: 600;
    color: #e2e8f0;
    border-bottom: 1px solid #2d3748;
    padding-bottom: 0.35rem;
  }
  .group-count {
    color: #718096;
    font-weight: 400;
  }
  :global(td.up) {
    color: #68d391;
    font-variant-numeric: tabular-nums;
  }
  :global(td.down) {
    color: #fc8181;
    font-variant-numeric: tabular-nums;
  }
</style>
