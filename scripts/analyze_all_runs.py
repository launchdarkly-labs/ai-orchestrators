#!/usr/bin/env python3
"""
Comprehensive analysis of all orchestrator runs from results directory.
Reads metadata from all available runs and creates detailed statistics.
"""

import json
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from collections import defaultdict

def load_metadata_files():
    """Load all metadata.json files from results directory."""
    results_dir = Path("results")
    runs = []

    for orch_dir in results_dir.iterdir():
        if orch_dir.is_dir() and orch_dir.name not in ['run_logs', '.DS_Store']:
            for file in orch_dir.glob("*metadata.json"):
                try:
                    with open(file, 'r') as f:
                        metadata = json.load(f)

                        # Extract orchestrator name (handle both old and new formats)
                        if 'orchestrator' in metadata and isinstance(metadata['orchestrator'], dict):
                            orch_name = metadata['orchestrator'].get('name', orch_dir.name)
                        elif 'orchestrator_name' in metadata:
                            orch_name = metadata['orchestrator_name']
                        else:
                            orch_name = orch_dir.name

                        # Extract execution details
                        if 'execution' in metadata:
                            exec_data = metadata['execution']
                            execution_time = exec_data.get('execution_time_seconds', 0)
                            total_tokens = exec_data.get('total_tokens', 0)
                        else:
                            execution_time = metadata.get('execution_time_seconds', 0)
                            total_tokens = metadata.get('total_tokens', 0)

                        # Extract task details
                        if 'task' in metadata:
                            papers_count = metadata['task'].get('input_papers_count', 0)
                            task_desc = metadata['task'].get('description', 'Unknown')
                        else:
                            papers_count = metadata.get('input_papers_count', 0)
                            task_desc = 'Research Gap Analysis'

                        # Get report file size
                        report_file = file.parent / file.name.replace('metadata.json', 'report.txt')
                        report_size = 0
                        if report_file.exists():
                            report_size = report_file.stat().st_size

                        # Determine dataset from timestamp/filename pattern
                        # Map timestamps to known datasets based on our runs
                        timestamp = file.name.split('_')[0] + '_' + file.name.split('_')[1] if '_' in file.name else 'unknown'

                        # Dataset mapping based on correct order from user
                        dataset_map = {
                            # Emergent Communication (first batch)
                            '20260128_113417': 'emergent_communication',    # AutoGen
                            '20260128_014823': 'emergent_communication',    # LangGraph
                            '20260127_203016': 'emergent_communication',    # OpenAI Swarm
                            '20260128_153442': 'emergent_communication',    # Strands

                            # Theorem Proving (second batch)
                            '20260128_140744': 'theorem_proving',    # AutoGen
                            '20260128_135155': 'theorem_proving',    # LangGraph
                            '20260128_135432': 'theorem_proving',    # OpenAI Swarm
                            '20260128_154020': 'theorem_proving',    # Strands

                            # Self Improvement (third batch)
                            '20260128_144158': 'self_improvement',   # AutoGen
                            '20260128_144222': 'self_improvement',   # LangGraph
                            '20260128_144710': 'self_improvement',   # OpenAI Swarm
                            '20260128_154743': 'self_improvement',   # Strands
                        }

                        # Try to determine from timestamp first
                        dataset_name = dataset_map.get(timestamp, 'unknown')

                        # If still unknown, try to infer from file path or other metadata
                        if dataset_name == 'unknown':
                            # Check if we have dataset info in metadata
                            if 'dataset' in metadata:
                                dataset_name = metadata['dataset']
                            elif 'task' in metadata and 'dataset' in metadata['task']:
                                dataset_name = metadata['task']['dataset']
                            else:
                                # Default based on paper count and timing patterns
                                dataset_name = 'unknown'

                        runs.append({
                            'orchestrator': orch_name.lower(),
                            'dataset': dataset_name,
                            'file_path': str(file),
                            'execution_time_seconds': execution_time,
                            'execution_time_minutes': execution_time / 60 if execution_time else 0,
                            'total_tokens': total_tokens,
                            'papers_analyzed': papers_count,
                            'report_size_bytes': report_size,
                            'report_size_chars': report_size,  # Approximate
                            'task': task_desc,
                            'timestamp': timestamp,
                            'status': 'completed'
                        })

                except Exception as e:
                    print(f"Error reading {file}: {e}")
                    continue

    return runs

def analyze_runs(runs):
    """Analyze all runs and generate statistics."""

    df = pd.DataFrame(runs)

    if df.empty:
        print("No runs found in results directory")
        return None

    # Overall statistics
    summary = {
        'total_runs': len(df),
        'orchestrators': df['orchestrator'].unique().tolist(),
        'total_execution_time_minutes': df['execution_time_minutes'].sum(),
        'average_execution_time_minutes': df['execution_time_minutes'].mean(),
        'total_tokens_processed': df['total_tokens'].sum(),
        'average_tokens_per_run': df['total_tokens'].mean(),
        'total_papers_analyzed': df['papers_analyzed'].sum(),
        'average_report_size_chars': df['report_size_chars'].mean()
    }

    # Per-orchestrator statistics
    orchestrator_stats = {}
    for orch in df['orchestrator'].unique():
        orch_df = df[df['orchestrator'] == orch]
        orchestrator_stats[orch] = {
            'runs': len(orch_df),
            'avg_execution_time_minutes': orch_df['execution_time_minutes'].mean(),
            'std_execution_time_minutes': orch_df['execution_time_minutes'].std(),
            'avg_tokens': orch_df['total_tokens'].mean(),
            'std_tokens': orch_df['total_tokens'].std(),
            'total_papers': orch_df['papers_analyzed'].sum(),
            'avg_report_size': orch_df['report_size_chars'].mean(),
            'tokens_per_second': orch_df['total_tokens'].sum() / orch_df['execution_time_seconds'].sum() if orch_df['execution_time_seconds'].sum() > 0 else 0,
            'datasets_tested': orch_df['dataset'].unique().tolist() if 'dataset' in orch_df.columns else []
        }

    return {
        'summary': summary,
        'orchestrator_stats': orchestrator_stats,
        'detailed_runs': runs
    }

def print_report(stats):
    """Print a formatted report."""

    if not stats:
        return

    print("\n" + "="*80)
    print("ORCHESTRATOR RUN ANALYSIS - COMPREHENSIVE REPORT")
    print("="*80)

    # Summary
    print("\n### OVERALL SUMMARY ###")
    summary = stats['summary']
    print(f"Total Runs Analyzed: {summary['total_runs']}")
    print(f"Orchestrators: {', '.join(summary['orchestrators'])}")
    print(f"Total Execution Time: {summary['total_execution_time_minutes']:.2f} minutes")
    print(f"Average Execution Time: {summary['average_execution_time_minutes']:.2f} minutes")
    print(f"Total Tokens Processed: {summary['total_tokens_processed']:,}")
    print(f"Average Tokens per Run: {summary['average_tokens_per_run']:,.0f}")
    print(f"Total Papers Analyzed: {summary['total_papers_analyzed']}")
    print(f"Average Report Size: {summary['average_report_size_chars']:,.0f} characters")

    # Per-Orchestrator Stats
    print("\n### PER-ORCHESTRATOR STATISTICS ###")
    for orch, orch_stats in stats['orchestrator_stats'].items():
        print(f"\n{orch.upper()}:")
        print(f"  Runs: {orch_stats['runs']}")
        print(f"  Average Execution Time: {orch_stats['avg_execution_time_minutes']:.2f} ± {orch_stats['std_execution_time_minutes']:.2f} minutes")
        print(f"  Average Tokens: {orch_stats['avg_tokens']:,.0f} ± {orch_stats['std_tokens']:,.0f}")
        print(f"  Processing Speed: {orch_stats['tokens_per_second']:.2f} tokens/second")
        print(f"  Total Papers Processed: {orch_stats['total_papers']}")
        print(f"  Average Report Size: {orch_stats['avg_report_size']:,.0f} characters")

    # Comparison
    print("\n### COMPARATIVE ANALYSIS ###")

    # Find fastest and most efficient
    orch_stats = stats['orchestrator_stats']
    if len(orch_stats) > 1:
        fastest = min(orch_stats.items(), key=lambda x: x[1]['avg_execution_time_minutes'])
        most_efficient = min(orch_stats.items(), key=lambda x: x[1]['avg_tokens'])

        print(f"\nFastest Orchestrator: {fastest[0]} ({fastest[1]['avg_execution_time_minutes']:.2f} min avg)")
        print(f"Most Token-Efficient: {most_efficient[0]} ({most_efficient[1]['avg_tokens']:,.0f} tokens avg)")

        # Speed comparison
        print("\nExecution Time Ranking:")
        sorted_by_time = sorted(orch_stats.items(), key=lambda x: x[1]['avg_execution_time_minutes'])
        for i, (orch, data) in enumerate(sorted_by_time, 1):
            print(f"  {i}. {orch}: {data['avg_execution_time_minutes']:.2f} minutes")

        # Token efficiency ranking
        print("\nToken Efficiency Ranking:")
        sorted_by_tokens = sorted(orch_stats.items(), key=lambda x: x[1]['avg_tokens'])
        for i, (orch, data) in enumerate(sorted_by_tokens, 1):
            print(f"  {i}. {orch}: {data['avg_tokens']:,.0f} tokens")

def save_to_files(stats):
    """Save statistics to files."""

    if not stats:
        return

    # Save as JSON
    with open('orchestrator_all_statistics.json', 'w') as f:
        clean_stats = json.loads(json.dumps(stats, default=str))
        json.dump(clean_stats, f, indent=2)
    print("\n✓ Statistics saved to orchestrator_all_statistics.json")

    # Save detailed runs as CSV
    df = pd.DataFrame(stats['detailed_runs'])
    df.to_csv('orchestrator_all_runs.csv', index=False)
    print("✓ Run details saved to orchestrator_all_runs.csv")

    # Create comparison matrix
    comparison_data = []
    for orch, data in stats['orchestrator_stats'].items():
        comparison_data.append({
            'Orchestrator': orch,
            'Runs': data['runs'],
            'Avg Time (min)': round(data['avg_execution_time_minutes'], 2),
            'Avg Tokens': int(data['avg_tokens']),
            'Tokens/sec': round(data['tokens_per_second'], 2),
            'Avg Report Size': int(data['avg_report_size']),
            'Datasets': data.get('datasets_tested', [])
        })

    comparison_df = pd.DataFrame(comparison_data)
    comparison_df.to_csv('orchestrator_comparison_matrix.csv', index=False)
    print("✓ Comparison matrix saved to orchestrator_comparison_matrix.csv")

def main():
    """Main entry point."""
    print("Analyzing all orchestrator runs from results directory...")

    # Load all metadata files
    runs = load_metadata_files()

    if not runs:
        print("No runs found in results directory")
        return

    print(f"Found {len(runs)} runs to analyze")

    # Analyze runs
    stats = analyze_runs(runs)

    # Print report
    print_report(stats)

    # Save to files
    save_to_files(stats)

    print("\n" + "="*80)
    print("Analysis complete!")
    print("="*80)

if __name__ == "__main__":
    main()