#!/usr/bin/env python3
"""
Download papers for research gap analysis with token-efficient section extraction.
Only extracts abstract, introduction, and conclusion sections.
"""

import arxiv
import json
import PyPDF2
import io
import requests
from pathlib import Path

def extract_key_sections_from_pdf(pdf_url):
    """
    Extract only abstract, introduction, and conclusion from PDF for token efficiency.
    """
    try:
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()

        pdf_file = io.BytesIO(response.content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)

        full_text = ""
        for page in pdf_reader.pages:
            full_text += page.extract_text() + "\n"

        # Extract sections (similar to extract_key_sections tool)
        text_lower = full_text.lower()
        sections = {}

        # Extract abstract
        import re
        abstract_match = re.search(r'abstract\s*(.{100,2000}?)(?:\n\n|\n\s*\n|introduction)', text_lower, re.IGNORECASE | re.DOTALL)
        if abstract_match:
            start_pos = abstract_match.start(1)
            end_pos = abstract_match.end(1)
            sections["abstract"] = full_text[start_pos:end_pos].strip()[:2000]
        else:
            # Fallback: first 300 words
            words = full_text.split()
            sections["abstract"] = " ".join(words[:300])

        # Extract introduction
        intro_match = re.search(r'introduction\s*(.{500,3000}?)(?:\n\n[0-9]|\nmethod|\nrelated work|\napproach)', text_lower, re.IGNORECASE | re.DOTALL)
        if intro_match:
            start_pos = intro_match.start(1)
            end_pos = intro_match.end(1)
            sections["introduction"] = full_text[start_pos:end_pos].strip()[:3000]
        else:
            # Fallback: text from around 300-800 words in (after abstract)
            words = full_text.split()
            if len(words) > 800:
                sections["introduction"] = " ".join(words[300:800])
            else:
                sections["introduction"] = ""

        # Extract conclusion
        conclusion_match = re.search(r'(conclusion|future work|discussion)\s*(.{300,2000}?)(?:\n\nreferences|\nacknowledg|\nappendix|$)', text_lower, re.IGNORECASE | re.DOTALL)
        if conclusion_match:
            start_pos = conclusion_match.start(2)
            end_pos = conclusion_match.end(2)
            sections["conclusion"] = full_text[start_pos:end_pos].strip()[:2000]
        else:
            # Fallback: last 300 words (before references/acknowledgements if possible)
            words = full_text.split()
            if len(words) > 300:
                # Try to find references section to exclude it
                ref_idx = -1
                for i in range(len(words) - 50, max(0, len(words) - 500), -1):
                    if words[i].lower() in ['references', 'bibliography', 'acknowledgements']:
                        ref_idx = i
                        break

                if ref_idx > 0 and ref_idx > 300:
                    sections["conclusion"] = " ".join(words[ref_idx-300:ref_idx])
                else:
                    sections["conclusion"] = " ".join(words[-300:])
            else:
                sections["conclusion"] = ""

        return sections

    except Exception as e:
        print(f"   Error extracting sections: {e}")
        return None


def download_papers_for_topic(query, max_results=10, start_date="2022-01-01", end_date="2025-01-21"):
    """
    Download papers for a specific research topic.

    Args:
        query (str): Search query (e.g., "chain-of-thought prompting")
        max_results (int): Number of papers to download (default 10)
        start_date (str): Start date for papers (YYYY-MM-DD)
        end_date (str): End date for papers (YYYY-MM-DD)

    Returns:
        list: List of papers with extracted sections
    """
    print(f"🔍 Searching ArXiv for: {query}")
    print(f"📅 Date range: {start_date} to {end_date}")
    print(f"📊 Max results: {max_results}")
    print()

    # Construct ArXiv search query with date filter
    search_query = f'{query} AND submittedDate:[{start_date.replace("-", "")} TO {end_date.replace("-", "")}]'

    # Search ArXiv - use Relevance sorting for category queries
    search = arxiv.Search(
        query=search_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
        sort_order=arxiv.SortOrder.Descending
    )

    papers = []

    for idx, result in enumerate(search.results(), 1):
        print(f"[{idx}/{max_results}] Processing: {result.title[:60]}...")

        # Extract basic metadata
        paper_data = {
            "id": result.entry_id.split("/")[-1],
            "title": result.title,
            "authors": ", ".join([author.name for author in result.authors]),
            "published": result.published.strftime("%Y-%m-%d"),
            "category": result.primary_category,
            "arxiv_url": result.entry_id,
            "pdf_url": result.pdf_url
        }

        # Extract key sections from PDF
        print(f"   📄 Extracting abstract, intro, conclusion...")
        sections = extract_key_sections_from_pdf(result.pdf_url)

        if sections and sections.get("abstract"):
            paper_data["abstract"] = sections["abstract"]
            paper_data["introduction"] = sections.get("introduction", "")
            paper_data["conclusion"] = sections.get("conclusion", "")

            total_chars = len(sections["abstract"]) + len(sections.get("introduction", "")) + len(sections.get("conclusion", ""))
            print(f"   ✓ Extracted {total_chars} chars (Abstract: {len(sections['abstract'])}, Intro: {len(sections.get('introduction', ''))}, Conclusion: {len(sections.get('conclusion', ''))})")

            papers.append(paper_data)
        else:
            print(f"   ✗ Failed to extract sections, skipping")

        print()

    return papers


def main():
    print("╔═══════════════════════════════════════════════════════╗")
    print("║  Research Gap Analysis - Paper Downloader            ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()

    # Example topics (user can modify)
    # Use ArXiv category syntax for better results: cat:CATEGORY AND keywords
    topics = {
        "1": {
            "name": "Chain-of-thought prompting in LLMs",
            "query": "cat:cs.CL AND (chain-of-thought OR CoT) AND reasoning",
            "years": 2
        },
        "2": {
            "name": "Retrieval-augmented generation (RAG)",
            "query": "cat:cs.CL AND (retrieval-augmented OR RAG) AND generation",
            "years": 2
        },
        "3": {
            "name": "Emergent communication in multi-agent RL",
            "query": "cat:cs.MA AND (emergent communication OR language emergence)",
            "years": 5
        },
        "4": {
            "name": "Few-shot prompting for code generation",
            "query": "cat:cs.SE AND few-shot AND code generation",
            "years": 2
        },
        "5": {
            "name": "Vision-language model grounding",
            "query": "cat:cs.CV AND vision-language AND grounding",
            "years": 2
        }
    }

    print("Available research topics:")
    for key, topic in topics.items():
        print(f"  {key}. {topic['name']} (last {topic['years']} years)")
    print()

    choice = input("Select topic (1-5) or enter custom query: ").strip()

    if choice in topics:
        topic = topics[choice]
        query = topic["query"]
        years_back = topic["years"]
    else:
        query = choice
        years_back = int(input("How many years back? (3-5): ").strip() or "3")

    # Calculate date range
    from datetime import datetime, timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years_back * 365)

    num_papers = int(input("How many papers? (8-15 recommended): ").strip() or "10")

    print()
    print(f"🔍 Query: {query}")
    print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"📊 Papers to download: {num_papers}")
    print()

    # Download papers
    papers = download_papers_for_topic(
        query=query,
        max_results=num_papers,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d")
    )

    if not papers:
        print("❌ No papers downloaded successfully")
        return

    # Save to JSON - use query-based filename
    import string
    # Clean query for filename (remove special chars, limit length)
    clean_query = query.lower()
    # Remove category prefix if present
    if "cat:" in clean_query:
        clean_query = clean_query.split("AND", 1)[-1] if "AND" in clean_query else clean_query
    # Keep only alphanumeric and spaces
    clean_query = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in clean_query)
    # Convert to snake case and limit length
    filename_base = '_'.join(clean_query.split())[:50]
    if not filename_base:
        filename_base = "gap_analysis_papers"

    output_file = Path(__file__).parent.parent / "data" / f"{filename_base}_papers.json"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(papers, f, indent=2)

    print("✨ Download complete!")
    print(f"📦 Saved {len(papers)} papers to: {output_file}")
    print()
    print("Token estimate:")
    total_chars = sum(
        len(p.get("abstract", "")) +
        len(p.get("introduction", "")) +
        len(p.get("conclusion", ""))
        for p in papers
    )
    print(f"  Total chars: {total_chars:,}")
    print(f"  Estimated tokens: {total_chars // 4:,} (~{(total_chars // 4) / 1000:.1f}K)")
    print()
    print("Next step: Run bootstrap to create agents")
    print("  python setup/bootstrap.py")


if __name__ == "__main__":
    main()
