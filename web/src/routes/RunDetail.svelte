<script lang="ts">
  import { onMount } from "svelte";
  import { fetchRun, type RunDetail } from "../lib/api";

  export let params: { id?: string } = {};

  let detail: RunDetail | null = null;
  let error: string | null = null;

  onMount(async () => {
    const id = Number(params.id);
    if (isNaN(id)) {
      error = "Invalid run ID";
      return;
    }
    try {
      detail = await fetchRun(id);
    } catch (e) {
      error = String(e);
    }
  });
</script>

{#if error}
  <p class="error">{error}</p>
{:else if !detail}
  <p class="loading">Loading…</p>
{:else}
  <div class="run-meta">
    <span>Run #{detail.run.id}</span>
    <span class="status status-{detail.run.status}">{detail.run.status}</span>
    <span>{new Date(detail.run.started_at).toLocaleString()}</span>
    <span>{detail.run.n_signals} signals · {detail.run.n_new_hits} new</span>
  </div>

  {#if detail.signals.length === 0}
    <p class="empty">No signals this run.</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Screener</th>
          <th>Score</th>
          <th>New</th>
          <th>Analysis</th>
        </tr>
      </thead>
      <tbody>
        {#each detail.signals as s}
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
