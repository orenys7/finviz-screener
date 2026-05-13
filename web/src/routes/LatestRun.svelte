<script lang="ts">
  import { onMount } from "svelte";
  import { fetchLatest, fetchManifest, type RunDetail } from "../lib/api";
  import SignalsByScreener from "../lib/SignalsByScreener.svelte";

  let detail: RunDetail | null = null;
  let error: string | null = null;
  let empty = false;

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
</script>

{#if error}
  <p class="error">{error}</p>
{:else if empty}
  <div class="page-head">
    <h1>Latest Scan</h1>
    <p class="subtitle">Awaiting first run.</p>
  </div>
  <p class="empty">No scans have run yet.</p>
{:else if !detail}
  <p class="loading">Loading…</p>
{:else}
  <div class="page-head">
    <h1>Equity Screener Results</h1>
    <p class="subtitle">
      Showing <strong>{detail.run.n_signals}</strong> signal{detail.run.n_signals === 1 ? "" : "s"}
      from run #{detail.run.id} · <strong>{detail.run.n_new_hits}</strong> new
    </p>
  </div>

  <div class="run-meta">
    <span class={`pill pill-${detail.run.status}`}>{detail.run.status}</span>
    <span>Run #{detail.run.id}</span>
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
