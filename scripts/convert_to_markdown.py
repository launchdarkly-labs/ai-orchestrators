#!/usr/bin/env python3
"""
Convert research gap analysis text reports to markdown format.
"""

import re
from pathlib import Path

def parse_report_to_markdown(report_text):
    """Convert a text report to clean markdown format."""

    # Find the main report content (between the box and end markers)
    # Look for the report box
    box_pattern = r'╔══════════════════════════════════════════════════════╗.*?╚══════════════════════════════════════════════════════╝'
    box_match = re.search(box_pattern, report_text, re.DOTALL)

    if box_match:
        # Find content after the box
        start = box_match.end()

        # Look for end markers
        # Check for ``` markers (some reports are wrapped)
        if '```' in report_text[:start]:
            # Find the closing ```
            end_match = re.search(r'```', report_text[start:])
            if end_match:
                content = report_text[start:start + end_match.start()]
            else:
                content = report_text[start:]
        else:
            content = report_text[start:]

        # Clean up any DEBUG or status messages at the end
        for marker in ['DEBUG |', '------------------------------------------------------------', '✅ Status:', '```']:
            pos = content.find(marker)
            if pos > 0:
                content = content[:pos]
    else:
        # No box found, try to extract main content
        content = report_text

    # Convert section headers
    content = re.sub(r'^=== (.*?) ===$', r'## \1', content, flags=re.MULTILINE)

    # Handle paper listings - make them proper lists
    content = re.sub(r'^\[(\d+)\] "', r'\n### Paper \1: "', content, flags=re.MULTILINE)

    # Bold the key fields
    content = re.sub(r'^(Authors|Published|ArXiv|Key Contribution):', r'- **\1**:', content, flags=re.MULTILINE)

    # Handle Gap/Direction entries with proper formatting
    content = re.sub(r'^\*\*Gap (\d+):(.*?)\*\*', r'\n### Gap \1:\2', content, flags=re.MULTILINE)
    content = re.sub(r'^\*\*Direction (\d+):(.*?)\*\*', r'\n### Research Direction \1:\2', content, flags=re.MULTILINE)

    # Handle field labels
    content = re.sub(r'^(Description|Evidence|Opportunity|Gap Addressed|Building On|Concrete Approach|First Steps|Expected Impact|Category):',
                     r'\n**\1**:', content, flags=re.MULTILINE)

    # Handle Approach sections
    content = re.sub(r'^\*\*Approach (\d+):(.*?)\*\*', r'\n### Approach \1:\2', content, flags=re.MULTILINE)

    # Handle Consensus/Contradiction sections
    content = re.sub(r'^\*\*Consensus (\d+):(.*?)\*\*', r'\n### Consensus \1:\2', content, flags=re.MULTILINE)
    content = re.sub(r'^\*\*Contradiction (\d+):(.*?)\*\*', r'\n### Contradiction \1:\2', content, flags=re.MULTILINE)
    content = re.sub(r'^\*\*Open Debate (\d+):(.*?)\*\*', r'\n### Open Debate \1:\2', content, flags=re.MULTILINE)

    # Clean up Analysis: tags
    content = re.sub(r'^\*\*Analysis:\*\*', r'\n**Analysis:**', content, flags=re.MULTILINE)

    # Handle numbered lists within sections (preserve indentation)
    content = re.sub(r'^(\s+)(\d+)\. ', r'\1\2. ', content, flags=re.MULTILINE)

    # Handle bullet points
    content = re.sub(r'^(\s*)- ', r'\1- ', content, flags=re.MULTILINE)

    # Clean up extra newlines
    content = re.sub(r'\n{3,}', '\n\n', content)

    # Add proper title
    title = "# Research Gap Analysis Report\n\n"

    return title + content.strip()

# Report file mapping
report_files = [
    # Emergent Communication
    ("autogen", "emergent_communication", "results/autogen/20260128_113417_autogen-20260128_113417_report.txt"),
    ("langgraph", "emergent_communication", "results/langgraph/20260128_014823_langgraph-20260128_014823_report.txt"),
    ("openai-swarm", "emergent_communication", "results/openai_swarm/20260127_203016_openai-swarm-20260127_202623_report.txt"),
    ("strands", "emergent_communication", "results/strands/20260128_153442_strands-20260128_153442_report.txt"),

    # Theorem Proving
    ("autogen", "theorem_proving", "results/autogen/20260128_140744_autogen-20260128_140744_report.txt"),
    ("langgraph", "theorem_proving", "results/langgraph/20260128_135155_langgraph-20260128_135155_report.txt"),
    ("openai-swarm", "theorem_proving", "results/openai_swarm/20260128_135432_openai-swarm-20260128_135245_report.txt"),
    ("strands", "theorem_proving", "results/strands/20260128_154020_strands-20260128_154020_report.txt"),

    # Self Improvement
    ("autogen", "self_improvement", "results/autogen/20260128_144158_autogen-20260128_144158_report.txt"),
    ("langgraph", "self_improvement", "results/langgraph/20260128_144222_langgraph-20260128_144222_report.txt"),
    ("openai-swarm", "self_improvement", "results/openai_swarm/20260128_144710_openai-swarm-20260128_144405_report.txt"),
    ("strands", "self_improvement", "results/strands/20260128_154743_strands-20260128_154743_report.txt"),
]

def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║  Convert Reports to Markdown                         ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    # Create output directory
    output_dir = Path("reports_markdown")
    output_dir.mkdir(exist_ok=True)
    print(f"📁 Output directory: {output_dir}")
    print()

    successful = 0
    failed = 0

    for orchestrator, dataset, report_path in report_files:
        report_file = Path(report_path)

        # Generate output filename
        output_name = f"{orchestrator}_{dataset}.md"
        output_file = output_dir / output_name

        print(f"Processing: {orchestrator} - {dataset}")
        print(f"  Input:  {report_path}")
        print(f"  Output: {output_file}")

        if not report_file.exists():
            print(f"  ❌ Report file not found: {report_file}")
            failed += 1
            print()
            continue

        try:
            # Read report
            with open(report_file, 'r') as f:
                report_text = f.read()

            # Convert to markdown
            markdown_content = parse_report_to_markdown(report_text)

            # Save markdown file
            with open(output_file, 'w') as f:
                f.write(markdown_content)

            print(f"  ✅ Markdown created successfully")
            successful += 1

        except Exception as e:
            print(f"  ❌ Error converting to markdown: {e}")
            failed += 1

        print()

    print("="*60)
    print(f"✨ Completed: {successful} successful, {failed} failed")
    print(f"📁 Markdown files saved to: {output_dir}")
    print()

if __name__ == "__main__":
    main()