<script lang="ts">
  import { onMount } from "svelte";
  import { fetchLatest, fetchManifest, type RunDetail, type SignalRow } from "../lib/api";

  let detail: RunDetail | null = null;
  let error: string | null = null;
  let empty = false;
  let sortKey: keyof SignalRow = "score";
  let sortAsc = false;

  onMount(async () => {
    try {
      const manifest = await fetchManifest();
      if (manifest.latest_run_id === null) {
        empty = true;
        return;
      }
      detail = await fetchLatest();
    } catch (e) {
      error = String(e);
    }
  });

  function sort(key: keyof SignalRow) {
    if (sortKey === key) {
      sortAsc = !sortAsc;
    } else {
      sortKey = key;
      sortAsc = key !== "score";
    }
  }

  $: sorted = detail
    ? [...detail.signals].sort((a, b) => {
        const av = a[sortKey];
        const bv = b[sortKey];
        const cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return sortAsc ? cmp : -cmp;
      })
    : [];

  function arrow(key: keyof SignalRow) {
    if (sortKey !== key) return "";
    return sortAsc ? " ▲" : " ▼";
  }
</script>

{#if error}
  <p class="error">{error}</p>
{:else if empty}
  <p class="empty">No scans have run yet.</p>
{:else if !detail}
  <p class="loading">Loading…</p>
{:else}
  <div class="run-meta">
    <span>Run #{detail.run.id}</span>
    <span class="status status-{detail.run.status}">{detail.run.status}</span>
    <span>{new Date(detail.run.started_at).toLocaleString()}</span>
    <span>{detail.run.n_signals} signals · {detail.run.n_new_hits} new</span>
  </div>

  {#if sorted.length === 0}
    <p class="empty">No signals this run.</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th on:click={() => sort("ticker")}>Ticker{arrow("ticker")}</th>
          <th on:click={() => sort("screener")}>Screener{arrow("screener")}</th>
          <th on:click={() => sort("score")}>Score{arrow("score")}</th>
          <th>New</th>
          <th>Analysis</th>
        </tr>
      </thead>
      <tbody>
        {#each sorted as s}
          <tr class={s.is_new_hit ? "new-hit" : ""}>
            <td>
              <a href="https://finviz.com/quote.ashx?t={s.ticker}" target="_blank"
                >{s.ticker}</a
              >
            </td>
            <td>{s.screener}</td>
            <td class="score score-{s.score}">{s.score}</td>
            <td>{s.is_new_hit ? "★" : ""}</td>
            <td class="analysis">{s.analysis}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
{/if}
