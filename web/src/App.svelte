<script lang="ts">
  import Router, { link } from "svelte-spa-router";
  import LatestRun from "./routes/LatestRun.svelte";
  import RunDetail from "./routes/RunDetail.svelte";
  import RunsList from "./routes/RunsList.svelte";

  const routes = {
    "/": LatestRun,
    "/runs": RunsList,
    "/runs/:id": RunDetail,
  };
</script>

<header>
  <nav>
    <a href="/" use:link class="brand">
      <span class="brand-mark">▲</span> FinvizScan
    </a>
    <div class="nav-links">
      <a href="/" use:link>Latest</a>
      <a href="/runs" use:link>All Runs</a>
    </div>
    <a class="github-link" href="https://github.com/orenys7/finviz-screener" target="_blank" rel="noopener">
      GitHub →
    </a>
  </nav>
</header>

<main>
  <Router {routes} />
</main>

<style>
  :global(:root) {
    --bg: #f8fafc;
    --surface: #ffffff;
    --border: #e5e7eb;
    --border-soft: #f1f5f9;
    --text: #0f172a;
    --text-muted: #64748b;
    --text-faint: #94a3b8;
    --primary: #10b981;
    --primary-soft: #d1fae5;
    --primary-softer: #ecfdf5;
    --danger: #ef4444;
    --danger-soft: #fee2e2;
    --warn: #f59e0b;
    --warn-soft: #fef3c7;
    --info: #6366f1;
    --info-soft: #e0e7ff;
  }

  :global(*) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(body) {
    font-family:
      "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }

  :global(a) {
    color: var(--text);
    text-decoration: none;
  }

  :global(h1) {
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--text);
  }

  :global(h2) {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
  }

  :global(table) {
    width: 100%;
    border-collapse: collapse;
    font-variant-numeric: tabular-nums;
  }

  :global(thead th) {
    text-align: left;
    padding: 0.6rem 0.9rem;
    background: transparent;
    color: var(--text-muted);
    font-weight: 500;
    font-size: 12px;
    cursor: pointer;
    user-select: none;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
  }

  :global(thead th:hover) {
    color: var(--text);
  }

  :global(tbody td) {
    padding: 0.85rem 0.9rem;
    border-bottom: 1px solid var(--border-soft);
    vertical-align: middle;
  }

  :global(tbody tr:last-child td) {
    border-bottom: none;
  }

  :global(tbody tr:hover td) {
    background: var(--primary-softer);
  }

  :global(tr.clickable) {
    cursor: pointer;
  }

  :global(.analysis) {
    max-width: 460px;
    color: var(--text-muted);
    font-size: 13px;
  }

  /* Status pills */
  :global(.pill) {
    display: inline-block;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
  }
  :global(.pill-ok) {
    background: var(--primary-soft);
    color: #047857;
  }
  :global(.pill-partial) {
    background: var(--warn-soft);
    color: #b45309;
  }
  :global(.pill-failed) {
    background: var(--danger-soft);
    color: #b91c1c;
  }
  :global(.pill-new) {
    background: var(--info-soft);
    color: #3730a3;
  }
  :global(.pill-up) {
    background: var(--primary-soft);
    color: #047857;
  }
  :global(.pill-down) {
    background: var(--danger-soft);
    color: #b91c1c;
  }
  :global(.pill-neutral) {
    background: var(--border-soft);
    color: var(--text-muted);
  }

  :global(.error) {
    color: #b91c1c;
    background: var(--danger-soft);
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin: 1rem 0;
  }

  :global(.loading),
  :global(.empty) {
    color: var(--text-muted);
    padding: 2rem 0;
    text-align: center;
  }

  :global(.run-meta) {
    display: flex;
    gap: 1rem;
    align-items: center;
    flex-wrap: wrap;
    padding: 0.5rem 0 1.25rem;
    color: var(--text-muted);
    font-size: 13px;
  }

  :global(.run-meta strong) {
    color: var(--text);
    font-weight: 600;
  }

  /* Header */
  header {
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }

  nav {
    max-width: 1200px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    gap: 2rem;
    height: 56px;
    padding: 0 1.5rem;
  }

  .brand {
    font-weight: 700;
    font-size: 16px;
    color: var(--text);
    letter-spacing: -0.01em;
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
  }

  .brand-mark {
    color: var(--primary);
    font-size: 18px;
  }

  .nav-links {
    display: flex;
    gap: 1.25rem;
    margin-right: auto;
  }

  .nav-links a {
    color: var(--text-muted);
    font-weight: 500;
    font-size: 13px;
    padding: 0.25rem 0;
    border-bottom: 2px solid transparent;
    transition: color 0.15s;
  }

  .nav-links a:hover {
    color: var(--text);
  }

  .github-link {
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
  }
  .github-link:hover {
    color: var(--primary);
  }

  main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1.75rem 1.5rem 3rem;
  }
</style>
