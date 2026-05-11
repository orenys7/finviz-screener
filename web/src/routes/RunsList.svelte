<script lang="ts">
  import { onMount } from "svelte";
  import { push } from "svelte-spa-router";
  import { fetchRuns, type RunSummary } from "../lib/api";

  let runs: RunSummary[] = [];
  let error: string | null = null;

  onMount(async () => {
    try {
      runs = await fetchRuns();
    } catch (e) {
      error = String(e);
    }
  });
</script>

{#if error}
  <p class="error">{error}</p>
{:else if runs.length === 0}
  <p class="loading">Loading…</p>
{:else}
  <table>
    <thead>
      <tr>
        <th>Run</th>
        <th>Started</th>
        <th>Status</th>
        <th>Signals</th>
        <th>New hits</th>
      </tr>
    </thead>
    <tbody>
      {#each runs as r}
        <tr class="clickable" on:click={() => push(`/runs/${r.id}`)}>
          <td>#{r.id}</td>
          <td>{new Date(r.started_at).toLocaleString()}</td>
          <td><span class="status status-{r.status}">{r.status}</span></td>
          <td>{r.n_signals}</td>
          <td>{r.n_new_hits}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}
