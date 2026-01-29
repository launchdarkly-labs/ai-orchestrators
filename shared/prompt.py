"""
Shared prompt building utilities for all orchestrators.
Provides consistent formatting of research papers into prompts.
"""

from typing import List, Dict, Any


def build_paper_prompt(papers: List[Dict[str, Any]], include_arxiv: bool = True) -> str:
    """
    Build a formatted prompt from a list of papers.

    Args:
        papers: List of paper dictionaries with title, authors, abstract, etc.
        include_arxiv: Whether to include ArXiv ID in the output

    Returns:
        Formatted prompt string with all papers
    """
    if not papers:
        return ""

    blocks = []
    for idx, paper in enumerate(papers, 1):
        paper_lines = [
            f"=== PAPER {idx} ===",
            f"Title: {paper.get('title', '')}",
            f"Authors: {paper.get('authors', '')}",
            f"Published: {paper.get('published', '')}",
        ]

        # Include ArXiv ID if requested (some orchestrators include it, others don't)
        if include_arxiv and 'id' in paper:
            paper_lines.append(f"ArXiv ID: {paper.get('id', '')}")

        paper_lines.extend([
            f"Category: {paper.get('category', '')}",
            "",
            "--- ABSTRACT ---",
            paper.get('abstract', '')
        ])

        blocks.append("\n".join(paper_lines))

    return "\n\n".join(blocks)


def format_paper_summary(paper: Dict[str, Any], index: int) -> str:
    """
    Format a single paper summary for display.

    Args:
        paper: Paper dictionary
        index: Paper index (1-based)

    Returns:
        Formatted summary string
    """
    title = paper.get('title', '').strip()[:70]
    if len(paper.get('title', '')) > 70:
        title += "..."

    authors = paper.get('authors', '').strip()[:50]
    if len(paper.get('authors', '')) > 50:
        authors += "..."

    return f"  [{index}] {title}\n      Authors: {authors}\n      Published: {paper.get('published', '')}"