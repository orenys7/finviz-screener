<script lang="ts">
  import { onMount } from "svelte";
  import { fetchRun, type RunDetail } from "../lib/api";
  import SignalsByScreener from "../lib/SignalsByScreener.svelte";

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
  <div class="page-head">
    <h1>Run #{detail.run.id}</h1>
    <p class="subtitle">
      <strong>{detail.run.n_signals}</strong> signal{detail.run.n_signals === 1 ? "" : "s"}
      · <strong>{detail.run.n_new_hits}</strong> new
    </p>
  </div>

  <div class="run-meta">
    <span class={`pill pill-${detail.run.status}`}>{detail.run.status}</span>
    <span>{new Date(detail.run.started_at).toLocaleString()}</span>
  </div>

  {#if detail.signals.length === 0}
    <p class="empty">No signals this run.</p>
  {:else}
    <SignalsByScreener signals={detail.signals} />
  {/if}
{/if}

<style>
  .page-head {
    margin-bottom: 1.5rem;
  }
  .subtitle {
    font-family: var(--font-sans);
    color: var(--text-muted);
    font-size: 14px;
    margin-top: 0.5rem;
  }
  .subtitle :global(strong) {
    color: var(--text);
    font-weight: 600;
  }
</style>
