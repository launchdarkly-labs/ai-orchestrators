"""
Domain tool for the research-gap-analysis graph.

One tool: ``fetch_paper`` — retrieve a paper's FULL text from arXiv on demand, for when
the abstract (the only per-paper content the agents receive) is insufficient. The node
prompts instruct agents to use it sparingly. ``TOOL_REGISTRY`` maps the tool name (as
attached to a node via ``config.tools``) to the callable; each runner binds it in its
own framework's style.
"""

import tempfile
import urllib.error

_MAX_CHARS = 15000  # a full paper is ~250k chars / ~60k tokens — cap what we feed back


def fetch_paper(arxiv_id: str) -> dict:
    """
    Fetch the full text of a paper from arXiv by its ID, for when the abstract is not
    enough to resolve a specific approach, contradiction, or gap.

    Use SPARINGLY — only when an abstract genuinely lacks the detail you need. Do not
    fetch every paper; most analysis should rely on the abstracts already provided.

    Args:
        arxiv_id (str): The arXiv ID of the paper, e.g. "2409.02645v2".

    Returns:
        dict: {"arxiv_id", "title", "text" (truncated full text), "truncated"} on success,
              or {"arxiv_id", "error"} if it can't be fetched (degrade to the abstract).
    """
    try:
        import arxiv
        from pypdf import PdfReader
    except Exception as e:  # pragma: no cover
        return {"arxiv_id": arxiv_id, "error": f"fetch unavailable ({e}); use the abstract"}

    try:
        result = next(arxiv.Client().results(arxiv.Search(id_list=[arxiv_id])))
        with tempfile.TemporaryDirectory() as d:
            path = result.download_pdf(dirpath=d)
            text = "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
    except StopIteration:
        return {"arxiv_id": arxiv_id, "error": f"paper {arxiv_id} not found on arXiv; use the abstract"}
    except urllib.error.HTTPError as e:
        return {"arxiv_id": arxiv_id, "error": f"arXiv unavailable (HTTP {e.code}); use the abstract"}
    except Exception as e:
        return {"arxiv_id": arxiv_id, "error": f"fetch failed ({str(e)[:60]}); use the abstract"}

    return {
        "arxiv_id": arxiv_id,
        "title": result.title,
        "text": text[:_MAX_CHARS],
        "truncated": len(text) > _MAX_CHARS,
    }


# Canonical ToolRegistry (name -> plain callable) — the shape the LD AI SDK expects
# (ldai.providers.types.ToolRegistry = Dict[str, Callable]). Each runner binds these to
# its framework (LangGraph/OpenAI via the companion packages; Strands/ADK natively).
TOOL_REGISTRY = {
    "fetch_paper": fetch_paper,
}
