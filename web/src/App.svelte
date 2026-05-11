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
    <a href="/" use:link class="brand">Finviz Screener</a>
    <a href="/" use:link>Latest</a>
    <a href="/runs" use:link>All Runs</a>
  </nav>
</header>

<main>
  <Router {routes} />
</main>

<style>
  :global(*) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(body) {
    font-family: system-ui, -apple-system, sans-serif;
    background: #0f1117;
    color: #e2e8f0;
    font-size: 14px;
    line-height: 1.5;
  }

  :global(a) {
    color: #63b3ed;
    text-decoration: none;
  }

  :global(a:hover) {
    text-decoration: underline;
  }

  :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin-top: 1rem;
  }

  :global(th) {
    text-align: left;
    padding: 0.5rem 0.75rem;
    background: #1a202c;
    color: #a0aec0;
    font-weight: 600;
    cursor: pointer;
    user-select: none;
    border-bottom: 1px solid #2d3748;
  }

  :global(th:hover) {
    color: #e2e8f0;
  }

  :global(td) {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #1a202c;
    vertical-align: top;
  }

  :global(tr.new-hit td) {
    background: rgba(99, 179, 237, 0.06);
  }

  :global(tr.clickable) {
    cursor: pointer;
  }

  :global(tr.clickable:hover td) {
    background: #1a202c;
  }

  :global(.analysis) {
    max-width: 500px;
    color: #a0aec0;
    font-size: 13px;
  }

  :global(.score) {
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  :global(.score-10),
  :global(.score-9) {
    color: #68d391;
  }

  :global(.score-8),
  :global(.score-7) {
    color: #f6e05e;
  }

  :global(.score-6),
  :global(.score-5) {
    color: #f6ad55;
  }

  :global(.score-4),
  :global(.score-3),
  :global(.score-2),
  :global(.score-1) {
    color: #fc8181;
  }

  :global(.status) {
    display: inline-block;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
  }

  :global(.status-ok) {
    background: #1c4532;
    color: #68d391;
  }

  :global(.status-partial) {
    background: #44371c;
    color: #f6e05e;
  }

  :global(.status-failed) {
    background: #3d1c1c;
    color: #fc8181;
  }

  :global(.run-meta) {
    display: flex;
    gap: 1rem;
    align-items: center;
    flex-wrap: wrap;
    padding: 0.75rem 0;
    color: #a0aec0;
    font-size: 13px;
  }

  :global(.error) {
    color: #fc8181;
    padding: 1rem 0;
  }

  :global(.loading),
  :global(.empty) {
    color: #a0aec0;
    padding: 1rem 0;
  }

  header {
    background: #1a202c;
    border-bottom: 1px solid #2d3748;
    padding: 0 1.5rem;
  }

  nav {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    height: 48px;
  }

  .brand {
    font-weight: 700;
    font-size: 16px;
    color: #e2e8f0;
    margin-right: auto;
  }

  main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1.5rem;
  }
</style>
