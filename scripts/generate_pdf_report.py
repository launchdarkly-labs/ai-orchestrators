#!/usr/bin/env python3
"""
Generate a nicely formatted PDF from the research gap analysis report.
"""

import re
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def extract_paper_titles(sections):
    """Extract paper titles from the ANALYZED PAPERS section."""
    paper_titles = {}

    for section_name, content in sections.items():
        if section_name.startswith("ANALYZED PAPERS"):
            # Parse paper entries
            paper_entries = re.split(r'\n(?=\[\d+\])', content)
            for entry in paper_entries:
                entry = entry.strip()
                if not entry:
                    continue

                # Extract paper ID and title
                # Format: [1] "Title"
                match = re.match(r'\[(\d+)\]\s+"([^"]+)"', entry)
                if match:
                    paper_id = match.group(1)
                    title = match.group(2)
                    # Shorten title if too long
                    if len(title) > 60:
                        title = title[:57] + "..."
                    paper_titles[paper_id] = title

    return paper_titles

def enhance_citations(text, paper_titles):
    """Replace bare citations like [1] with [1: Short Title]."""
    def replace_citation(match):
        paper_id = match.group(1)
        if paper_id in paper_titles:
            return f"[{paper_id}: {paper_titles[paper_id]}]"
        return match.group(0)

    # Match citations like [1], [2], [X], [Y], [Z] but not inside quotes
    text = re.sub(r'\[(\d+)\]', replace_citation, text)
    return text

def parse_report(report_text):
    """Parse the report text into structured sections."""
    # The structure is: ```\n╔box╗\n...content...\n```DEBUG
    # So we need to find content between the opening ``` and closing ```

    # Find opening ``` followed by the box
    box_pattern = r'```\s*\n╔══════════════════════════════════════════════════════╗'
    box_match = re.search(box_pattern, report_text)

    if not box_match:
        raise ValueError("Could not find report start marker with ```")

    # Start after the box and box title
    report_start = box_match.end()

    # Skip the box header lines (║ title ║ and ╚═══╝)
    # Find the closing box line ╚
    closing_box = report_text.find('╚══════════════════════════════════════════════════════╝', report_start)
    if closing_box > 0:
        report_start = closing_box + len('╚══════════════════════════════════════════════════════╝')

    # Find the closing ``` (which might have DEBUG immediately after)
    end_match = re.search(r'```(?=DEBUG|\s|$)', report_text[report_start:])
    if end_match:
        report_text = report_text[report_start:report_start + end_match.start()]
    else:
        # If no closing ```, just take everything after the box
        report_text = report_text[report_start:]
        # Stop at DEBUG logs
        end_markers = [
            report_text.find('DEBUG |'),
            report_text.find('------------------------------------------------------------'),
            report_text.find('✅ Status:'),
        ]
        end_markers = [m for m in end_markers if m > 0]
        if end_markers:
            report_text = report_text[:min(end_markers)]

    sections = {}
    current_section = None
    current_content = []

    lines = report_text.split('\n')

    for line in lines:
        # Check if this is a section header (with possible trailing spaces)
        stripped_line = line.rstrip()
        if stripped_line.startswith('===') and stripped_line.endswith('==='):
            # Save previous section
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()

            # Start new section
            current_section = stripped_line.strip('= ').strip()
            current_content = []
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()

    return sections

def create_pdf(sections, output_path):
    """Generate a nicely formatted PDF from the sections."""
    # Extract paper titles for citation enhancement
    paper_titles = extract_paper_titles(sections)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    # Create custom styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    section_style = ParagraphStyle(
        'CustomSection',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#283593'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold',
        keepWithNext=True  # Prevent breaking after headers
    )

    subsection_style = ParagraphStyle(
        'CustomSubsection',
        parent=styles['Heading3'],
        fontSize=13,
        textColor=colors.HexColor('#3949ab'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold',
        keepWithNext=True  # Prevent breaking after headers
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=10,
        wordWrap='CJK'  # Better word wrapping
    )

    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['BodyText'],
        fontSize=11,
        leading=16,
        leftIndent=20,
        spaceAfter=6,
        wordWrap='CJK'
    )

    paper_style = ParagraphStyle(
        'PaperEntry',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        leftIndent=15,
        spaceAfter=8,
        fontName='Helvetica',
        wordWrap='CJK'
    )

    # Build the PDF content
    story = []

    # Title
    story.append(Paragraph("RESEARCH GAP ANALYSIS REPORT", title_style))
    story.append(Spacer(1, 0.2*inch))

    # Section order (with optional EXECUTION METADATA)
    section_order = [
        "EXECUTION METADATA",
        "ANALYZED PAPERS (12 papers)",
        "RESEARCH FIELD OVERVIEW",
        "MAJOR APPROACHES",
        "KEY FINDINGS & CONSENSUS",
        "CONTRADICTIONS & OPEN DEBATES",
        "IDENTIFIED RESEARCH GAPS",
        "RECOMMENDED RESEARCH DIRECTIONS",
        "SUMMARY"
    ]

    for section_name in section_order:
        if section_name not in sections:
            continue

        content = sections[section_name]

        # Add section header
        story.append(Paragraph(section_name, section_style))

        # Process content based on section
        if section_name.startswith("ANALYZED PAPERS"):
            # Parse paper entries
            paper_entries = re.split(r'\n(?=\[\d+\])', content)
            for entry in paper_entries:
                entry = entry.strip()
                if not entry:
                    continue

                # Format paper entry
                lines = entry.split('\n')
                formatted_lines = []
                for line in lines:
                    line = line.strip()
                    if line.startswith('['):
                        # Paper ID and title
                        formatted_lines.append(f"<b>{line}</b>")
                    elif line:
                        formatted_lines.append(line)

                paper_html = '<br/>'.join(formatted_lines)
                story.append(Paragraph(paper_html, paper_style))
                story.append(Spacer(1, 0.05*inch))

        elif "APPROACHES" in section_name or "FINDINGS" in section_name or "CONTRADICTIONS" in section_name:
            # Handle sections with subsections and bullet points
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Enhance citations in this paragraph
                para = enhance_citations(para, paper_titles)

                # Check if it's a subsection (starts with **)
                if para.startswith('**'):
                    # Extract subsection title
                    match = re.match(r'\*\*(.*?)\*\*(.*)$', para, re.DOTALL)
                    if match:
                        subsection_title = match.group(1)
                        subsection_content = match.group(2).strip()

                        story.append(Paragraph(subsection_title, subsection_style))
                        if subsection_content:
                            story.append(Paragraph(subsection_content, body_style))
                elif para.startswith('-'):
                    # Bullet point
                    bullet_text = para[1:].strip()
                    story.append(Paragraph(f"• {bullet_text}", bullet_style))
                else:
                    story.append(Paragraph(para, body_style))

        elif "RESEARCH GAPS" in section_name:
            # Handle gap entries with Gap 1, Gap 2, etc.
            gap_entries = re.split(r'\n(?=\*\*Gap \d+:)', content)
            for entry in gap_entries:
                entry = entry.strip()
                if not entry:
                    continue

                # Parse gap entry
                lines = entry.split('\n')
                gap_title = ""
                gap_parts = {}
                current_part = None

                for line in lines:
                    line = line.strip()
                    if line.startswith('**Gap'):
                        # Extract gap title
                        match = re.match(r'\*\*Gap \d+: (.*?)\*\*', line)
                        if match:
                            gap_title = match.group(0).replace('**', '')
                    elif line.startswith('Description:'):
                        current_part = 'Description'
                        gap_parts[current_part] = line.replace('Description:', '').strip()
                    elif line.startswith('Evidence:'):
                        current_part = 'Evidence'
                        gap_parts[current_part] = line.replace('Evidence:', '').strip()
                    elif line.startswith('Opportunity:'):
                        current_part = 'Opportunity'
                        gap_parts[current_part] = line.replace('Opportunity:', '').strip()
                    elif current_part and line:
                        gap_parts[current_part] += ' ' + line

                if gap_title:
                    story.append(Paragraph(gap_title, subsection_style))

                    for part_name, part_content in gap_parts.items():
                        # Enhance citations in gap content
                        part_content = enhance_citations(part_content, paper_titles)
                        story.append(Paragraph(f"<b>{part_name}:</b> {part_content}", body_style))

                    story.append(Spacer(1, 0.1*inch))

        elif "RECOMMENDED" in section_name:
            # Handle both simple numbered lists and detailed recommendation format
            # Check if content has structured recommendations (with **Direction)
            if '**Direction' in content:
                # New detailed format
                rec_entries = re.split(r'\n(?=\*\*Direction \d+:)', content)
                for entry in rec_entries:
                    entry = entry.strip()
                    if not entry:
                        continue

                    # Parse recommendation entry
                    lines = entry.split('\n')
                    rec_title = ""
                    rec_parts = {}
                    current_part = None

                    for line in lines:
                        line = line.strip()
                        if line.startswith('**Direction'):
                            # Extract recommendation title
                            match = re.match(r'\*\*Direction \d+: (.*?)\*\*(.*)$', line)
                            if match:
                                rec_title = match.group(0).replace('**', '')
                                priority_info = match.group(2).strip()
                                if priority_info:
                                    rec_title += " " + priority_info
                        elif line.startswith('Gap Addressed:'):
                            current_part = 'Gap Addressed'
                            rec_parts[current_part] = line.replace('Gap Addressed:', '').strip()
                        elif line.startswith('Building On:'):
                            current_part = 'Building On'
                            rec_parts[current_part] = line.replace('Building On:', '').strip()
                        elif line.startswith('Concrete Approach:'):
                            current_part = 'Concrete Approach'
                            rec_parts[current_part] = line.replace('Concrete Approach:', '').strip()
                        elif line.startswith('First Steps:'):
                            current_part = 'First Steps'
                            rec_parts[current_part] = line.replace('First Steps:', '').strip()
                        elif line.startswith('Expected Impact:'):
                            current_part = 'Expected Impact'
                            rec_parts[current_part] = line.replace('Expected Impact:', '').strip()
                        elif current_part and line:
                            rec_parts[current_part] += ' ' + line

                    if rec_title:
                        # Enhance citations in title
                        rec_title = enhance_citations(rec_title, paper_titles)
                        story.append(Paragraph(rec_title, subsection_style))

                        for part_name, part_content in rec_parts.items():
                            # Enhance citations in recommendation content
                            part_content = enhance_citations(part_content, paper_titles)
                            story.append(Paragraph(f"<b>{part_name}:</b> {part_content}", body_style))

                        story.append(Spacer(1, 0.1*inch))
            else:
                # Old simple numbered list format
                items = re.split(r'\n(?=\d+\.)', content)
                for item in items:
                    item = item.strip()
                    if not item:
                        continue
                    # Enhance citations in recommendations
                    item = enhance_citations(item, paper_titles)
                    story.append(Paragraph(item, bullet_style))

        else:
            # Default: treat as regular paragraphs
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                para = para.strip()
                if para:
                    # Enhance citations in all other sections
                    para = enhance_citations(para, paper_titles)
                    story.append(Paragraph(para, body_style))

        story.append(Spacer(1, 0.15*inch))

    # Build PDF
    doc.build(story)
    print(f"✅ PDF generated successfully: {output_path}")

def main():
    import sys

    print("╔══════════════════════════════════════════════════════╗")
    print("║  Generate PDF Report                                  ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()

    # Get report file from argument or use latest in results/strands/
    project_root = Path(__file__).parent.parent

    if len(sys.argv) > 1:
        report_file = Path(sys.argv[1])
    else:
        # Find latest report in results/strands/
        results_dir = project_root / "results" / "strands"
        if not results_dir.exists():
            print(f"❌ No results directory found: {results_dir}")
            print("   Run the gap analysis first:")
            print("   python orchestrators/strands/run_gap_analysis.py")
            return

        report_files = sorted(results_dir.glob("*_gap_analysis_report.txt"), reverse=True)
        if not report_files:
            print(f"❌ No report files found in: {results_dir}")
            print("   Run the gap analysis first:")
            print("   python orchestrators/strands/run_gap_analysis.py")
            return

        report_file = report_files[0]
        print(f"📄 Using latest report: {report_file.name}")

    if not report_file.exists():
        print(f"❌ Report file not found: {report_file}")
        return

    print(f"📄 Reading report from: {report_file}")
    with open(report_file, 'r') as f:
        report_text = f.read()

    # Parse the report
    print("🔄 Parsing report sections...")
    sections = parse_report(report_text)
    print(f"   Found {len(sections)} sections")

    # Generate PDF with same name as report
    output_file = report_file.with_suffix('.pdf')
    print(f"📊 Generating PDF...")
    create_pdf(sections, output_file)

    print()
    print(f"✨ Done! PDF saved to: {output_file}")
    print()

if __name__ == "__main__":
    main()
