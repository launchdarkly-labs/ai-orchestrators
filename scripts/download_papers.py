#!/usr/bin/env python3
"""
Download arXiv papers for a research topic, to use as the experiment's query set.

Standalone — separate from the experiment. Writes ``data/<topic>_papers.json``; point the
experiment at it with:

    python scripts/run_experiment.py --data data/<that_file>.json

Abstracts come straight from arXiv metadata (``result.summary``) — clean and fast, no PDF
parsing. The agents analyze abstracts; the ``fetch_paper`` tool pulls full text on demand
at run time when an abstract isn't enough.

    # non-interactive
    python scripts/download_papers.py --query "cat:cs.AI AND (llm agents OR agentic)" --max-results 12
    # interactive menu (no args)
    python scripts/download_papers.py
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import arxiv


_SAFETY_CEILING = 300  # guard against an accidentally broad query, not a sampling knob


def download_papers_for_topic(query, max_results=None, years_back=3):
    """Search arXiv for ``query`` and return paper dicts (abstracts only — no PDF parsing).

    Gap analysis needs the COMPLETE recent literature on a narrow topic, so by default
    this fetches ALL matches (up to a safety ceiling). Pick a specific query rather than
    capping the results — a capped broad query yields gaps that are artifacts of the
    sample, not real gaps in the topic.
    """
    end = datetime.now()
    start = end - timedelta(days=years_back * 365)
    search_query = f"{query} AND submittedDate:[{start:%Y%m%d} TO {end:%Y%m%d}]"
    # `is None` (not truthiness) so an explicit 0 means "no papers", not "the ceiling".
    cap = _SAFETY_CEILING if max_results is None else max_results
    print(f"🔍 {query}  ({start:%Y-%m-%d} → {end:%Y-%m-%d}, "
          f"{'ALL matches (ceiling %d)' % cap if max_results is None else 'max %d' % cap})")

    search = arxiv.Search(
        query=search_query,
        max_results=cap,
        sort_by=arxiv.SortCriterion.Relevance,
        sort_order=arxiv.SortOrder.Descending,
    )
    papers = []
    for idx, result in enumerate(arxiv.Client().results(search), 1):
        papers.append({
            "id": result.entry_id.split("/")[-1],
            "title": result.title,
            "authors": ", ".join(a.name for a in result.authors),
            "published": result.published.strftime("%Y-%m-%d"),
            "category": result.primary_category,
            "arxiv_url": result.entry_id,
            "pdf_url": result.pdf_url,
            "abstract": (result.summary or "").strip(),
        })
        print(f"  [{idx}] {result.title[:70]}")
    if cap and len(papers) >= cap and max_results is None:
        print(f"⚠️  hit the {cap}-paper ceiling — the query is too broad for honest gap "
              f"analysis. Narrow it (quoted phrases help) so the set IS the topic's literature.")
    return papers


def _filename_for(query):
    clean = query.lower()
    if "cat:" in clean:  # drop the category prefix, keep the keywords
        clean = clean.split("and", 1)[-1] if "and" in clean else clean
    clean = "".join(c if c.isalnum() or c.isspace() else " " for c in clean)
    base = "_".join(clean.split())[:50] or "topic"
    return f"{base}_papers.json"


_MENU = {
    "1": ("Chain-of-thought reasoning in LLMs", "cat:cs.CL AND (chain-of-thought OR CoT) AND reasoning", 2),
    "2": ("Retrieval-augmented generation (RAG)", "cat:cs.CL AND (retrieval-augmented OR RAG) AND generation", 2),
    "3": ("Emergent communication in multi-agent RL", "cat:cs.MA AND (emergent communication OR language emergence)", 5),
    "4": ("Few-shot prompting for code generation", "cat:cs.SE AND few-shot AND code generation", 2),
    "5": ("Vision-language model grounding", "cat:cs.CV AND vision-language AND grounding", 2),
}


def main():
    ap = argparse.ArgumentParser(description="Download arXiv papers for a topic into data/.")
    ap.add_argument("--query", help="a NARROW arXiv query, e.g. 'all:\"process reward model\"'")
    ap.add_argument("--max-results", type=int, default=None,
                    help="safety cap only — default fetches ALL matches; narrow the query "
                         "instead of capping (gap analysis needs the topic's full literature)")
    ap.add_argument("--years-back", type=int, default=3)
    ap.add_argument("--output", help="output path (default: data/<topic>_papers.json)")
    args = ap.parse_args()

    query, years_back, max_results = args.query, args.years_back, args.max_results
    if not query:  # interactive menu fallback
        print("Topics:")
        for k, (name, _, yrs) in _MENU.items():
            print(f"  {k}. {name} (last {yrs}y)")
        choice = input("Select 1-5 or enter a custom arXiv query: ").strip()
        if choice in _MENU:
            _, query, years_back = _MENU[choice]
        else:
            query = choice
            years_back = int(input("Years back? [3]: ").strip() or "3")
        cap_raw = input("Max papers? [all matches]: ").strip().lower()
        try:
            max_results = int(cap_raw) if cap_raw and cap_raw != "all" else None
        except ValueError:
            print(f"  (didn't understand {cap_raw!r} — fetching all matches)")
            max_results = None

    papers = download_papers_for_topic(query, max_results=max_results, years_back=years_back)
    if not papers:
        print("❌ No papers found for that query.")
        return

    out = Path(args.output) if args.output else Path(__file__).parent.parent / "data" / _filename_for(query)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(papers, indent=2))
    print(f"\n✨ Saved {len(papers)} papers → {out}")
    print(f"   Run the experiment over it:\n   python scripts/run_experiment.py --data {out}")


if __name__ == "__main__":
    main()
