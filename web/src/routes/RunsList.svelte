<script lang="ts">
  import { onMount } from "svelte";
  import { push } from "svelte-spa-router";
  import { fetchRuns, type RunSummary } from "../lib/api";

  let runs: RunSummary[] = [];
  let error: string | null = null;
  let loaded = false;

  onMount(async () => {
    try {
      runs = await fetchRuns();
    } catch (e) {
      error = String(e);
    } finally {
      loaded = true;
    }
  });
</script>

<div class="page-head">
  <h1>All Runs</h1>
  <p class="subtitle">
    {#if loaded}<strong>{runs.length}</strong> total{:else}Loading…{/if}
  </p>
</div>

{#if error}
  <p class="error">{error}</p>
{:else if !loaded}
  <p class="loading">Loading…</p>
{:else if runs.length === 0}
  <p class="empty">No runs yet.</p>
{:else}
  <div class="card">
    <table>
      <thead>
        <tr>
          <th>Run</th>
          <th>Started</th>
          <th>Status</th>
          <th class="num">Signals</th>
          <th class="num">New hits</th>
        </tr>
      </thead>
      <tbody>
        {#each runs as r}
          <tr class="clickable" on:click={() => push(`/runs/${r.id}`)}>
            <td><strong>#{r.id}</strong></td>
            <td>{new Date(r.started_at).toLocaleString()}</td>
            <td><span class={`pill pill-${r.status}`}>{r.status}</span></td>
            <td class="num">{r.n_signals}</td>
            <td class="num">{r.n_new_hits}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .page-head {
    margin-bottom: 1rem;
  }
  .subtitle {
    color: var(--text-muted);
    font-size: 14px;
    margin-top: 0.35rem;
  }
  .subtitle :global(strong) {
    color: var(--text);
    font-weight: 600;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
  }
  :global(table th.num),
  :global(table td.num) {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
</style>
