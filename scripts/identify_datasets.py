#!/usr/bin/env python3
"""
Identify datasets from report files by analyzing paper titles.
"""

import os
import re
from pathlib import Path

def identify_dataset_from_report(report_file):
    """Identify dataset from report content based on paper titles."""

    try:
        with open(report_file, 'r') as f:
            content = f.read()[:5000]  # Read first 5000 chars

        # Keywords for each dataset type
        theorem_keywords = [
            'theorem', 'proof', 'mathematical', 'lean', 'coq', 'isabelle',
            'formal verification', 'automated reasoning', 'logic', 'sat',
            'smt', 'verification', 'proving'
        ]

        self_improvement_keywords = [
            'self-improvement', 'self improvement', 'reflection', 'self-reflection',
            'meta-learning', 'introspection', 'self-critique', 'self critique',
            'self-evaluation', 'self evaluation', 'adaptation', 'lifelong learning'
        ]

        emergent_keywords = [
            'emergent', 'communication', 'language evolution', 'multi-agent',
            'signaling', 'emergence', 'protocol', 'grounded language',
            'referential', 'compositional'
        ]

        content_lower = content.lower()

        # Count keyword matches
        theorem_score = sum(1 for kw in theorem_keywords if kw in content_lower)
        self_score = sum(1 for kw in self_improvement_keywords if kw in content_lower)
        emergent_score = sum(1 for kw in emergent_keywords if kw in content_lower)

        # Determine dataset based on highest score
        if theorem_score > self_score and theorem_score > emergent_score:
            return 'theorem_proving'
        elif self_score > theorem_score and self_score > emergent_score:
            return 'self_improvement'
        elif emergent_score > theorem_score and emergent_score > self_score:
            return 'emergent_communication'
        else:
            return 'unknown'

    except Exception as e:
        print(f"Error reading {report_file}: {e}")
        return 'unknown'

def update_dataset_mappings():
    """Generate dataset mappings for all report files."""

    results_dir = Path("results")
    mappings = {}

    for orch_dir in results_dir.iterdir():
        if orch_dir.is_dir() and orch_dir.name not in ['run_logs', '.DS_Store']:
            for report_file in orch_dir.glob("*report.txt"):
                # Extract timestamp from filename
                parts = report_file.name.split('_')
                if len(parts) >= 2:
                    timestamp = f"{parts[0]}_{parts[1]}"
                    dataset = identify_dataset_from_report(report_file)
                    mappings[timestamp] = dataset
                    print(f"{orch_dir.name}/{timestamp}: {dataset}")

    return mappings

def main():
    """Main entry point."""
    print("Identifying datasets from report files...")
    print("="*50)

    mappings = update_dataset_mappings()

    print("\n" + "="*50)
    print("Dataset mappings for analyze_all_runs.py:")
    print("="*50)

    print("\ndataset_map = {")
    for timestamp, dataset in sorted(mappings.items()):
        print(f"    '{timestamp}': '{dataset}',")
    print("}")

    # Count by dataset
    dataset_counts = {}
    for dataset in mappings.values():
        dataset_counts[dataset] = dataset_counts.get(dataset, 0) + 1

    print("\n" + "="*50)
    print("Summary:")
    for dataset, count in sorted(dataset_counts.items()):
        print(f"  {dataset}: {count} runs")

if __name__ == "__main__":
    main()