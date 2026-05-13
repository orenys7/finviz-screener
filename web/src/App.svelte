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
      <span class="brand-mark">◆</span> FinvizScan
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
    /* Emerald Minimalist palette */
    --primary: #1f6f5f;
    --secondary: #2fa084;
    --accent: #6fcf97;
    --bg: #eeeeee;
    --surface: #ffffff;
    --border: #d1d1d1;
    --border-soft: #e5e5e5;

    /* Semantic aliases */
    --primary-soft: #d3ece5;
    --primary-softer: #eaf5f1;
    --danger: #ef4444;
    --danger-soft: #fee2e2;
    --warn: #f59e0b;
    --warn-soft: #fef3c7;

    /* Text */
    --text: #1a1a1a;
    --text-muted: #6b7280;
    --text-faint: #9ca3af;

    /* Typography */
    --font-serif: "Lora", "Calluna", Georgia, serif;
    --font-sans: "Inter", system-ui, -apple-system, sans-serif;
  }

  :global(*) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(body) {
    font-family: var(--font-sans);
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
    font-family: var(--font-serif);
    font-size: 24px;
    font-weight: 600;
    color: var(--primary);
  }

  :global(h2) {
    font-family: var(--font-serif);
    font-size: 14px;
    font-weight: 600;
    color: var(--primary);
  }

  :global(table) {
    width: 100%;
    border-collapse: collapse;
    font-variant-numeric: tabular-nums;
  }

  :global(thead th) {
    text-align: left;
    padding: 0.72rem 1.08rem;
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
    padding: 1.02rem 1.08rem;
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
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.03em;
  }
  :global(.pill-ok) {
    background: var(--primary-soft);
    color: var(--primary);
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
    background: var(--primary-soft);
    color: var(--secondary);
  }
  :global(.pill-up) {
    background: var(--primary-soft);
    color: var(--primary);
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
    padding: 0.9rem 1.2rem;
    border-radius: 6px;
    border: 1px solid var(--danger);
    margin: 1rem 0;
  }

  :global(.loading),
  :global(.empty) {
    color: var(--text-muted);
    padding: 2.4rem 0;
    text-align: center;
  }

  :global(.run-meta) {
    display: flex;
    gap: 1rem;
    align-items: center;
    flex-wrap: wrap;
    padding: 0.6rem 0 1.5rem;
    color: var(--text-muted);
    font-size: 13px;
  }

  :global(.run-meta strong) {
    color: var(--text);
    font-weight: 600;
  }

  /* Header — flat nav on bg */
  header {
    background: var(--bg);
    border-bottom: 1px solid var(--border);
  }

  nav {
    max-width: 1200px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    gap: 2rem;
    height: 56px;
    padding: 0 1.8rem;
  }

  .brand {
    font-family: var(--font-serif);
    font-weight: 600;
    font-size: 17px;
    color: var(--primary);
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }

  .brand-mark {
    color: var(--secondary);
    font-size: 16px;
    font-style: normal;
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
    transition: color 0.15s, border-color 0.15s;
  }

  .nav-links a:hover {
    color: var(--primary);
    border-bottom-color: var(--accent);
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
    padding: 2.1rem 1.8rem 3.6rem;
  }
</style>
