#!/usr/bin/env python3
"""
Comprehensive analysis of orchestrator runs from log files.
Creates a dataset with statistics from multiple orchestrators and datasets.
"""

import json
import re
from pathlib import Path
from datetime import datetime
import pandas as pd

# Known completed runs with statistics extracted from logs
completed_runs = [
    {
        'orchestrator': 'strands',
        'dataset': 'theorem_proving',
        'dataset_full': 'cat_cs_ai_and_theorem_proving_or_mathematical_reasoning',
        'log_file': 'strands_theorem_test.log',
        'execution_id': 'strands-20260128_154020',
        'execution_time_seconds': 323.81,
        'execution_time_minutes': 5.40,
        'total_tokens': 101492,
        'input_tokens': 86472,
        'output_tokens': 15020,
        'iterations': 3,
        'agent_count': 3,
        'papers_analyzed': 12,
        'report_size_chars': 28680,
        'status': 'completed',
        'tokens_per_second': 313.46,
        'output_to_input_ratio': 0.1737,
        'chars_per_output_token': 1.91,
        'tokens_per_agent': 33831,
        'tokens_per_paper': 8458,
        'agent_details': [
            {'name': 'Research Approach Analyzer', 'tokens': 32487, 'ttft': 7.27},
            {'name': 'Contradiction Detection Specialist', 'tokens': 39265, 'ttft': 15.27},
            {'name': 'Research Gap Synthesizer', 'tokens': 29740, 'ttft': 34.94}
        ]
    },
    {
        'orchestrator': 'strands',
        'dataset': 'self_improvement',
        'dataset_full': 'cat_cs_ai_and_self_improvement_or_self_reflection',
        'log_file': 'strands_self_improvement.log',
        'execution_id': 'strands-20260128_154743',
        'execution_time_seconds': 434.34,
        'execution_time_minutes': 7.24,
        'total_tokens': 117564,
        'input_tokens': 97578,
        'output_tokens': 19986,
        'iterations': 3,
        'agent_count': 3,
        'papers_analyzed': 12,
        'report_size_chars': 36933,
        'status': 'completed',
        'tokens_per_second': 270.74,
        'output_to_input_ratio': 0.2049,
        'chars_per_output_token': 1.85,
        'tokens_per_agent': 39188,
        'tokens_per_paper': 9797,
        'agent_details': [
            {'name': 'Research Approach Analyzer', 'tokens': 36199, 'ttft': 9.55},
            {'name': 'Contradiction Detection Specialist', 'tokens': 45542, 'ttft': 20.10},
            {'name': 'Research Gap Synthesizer', 'tokens': 35823, 'ttft': 47.66}
        ]
    }
]

def create_detailed_statistics():
    """Create comprehensive statistics from the runs."""

    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(completed_runs)

    # Create summary statistics
    summary = {
        'orchestrators': df['orchestrator'].unique().tolist(),
        'datasets': df['dataset'].unique().tolist(),
        'total_runs': len(df),
        'completed_runs': len(df[df['status'] == 'completed']),
        'failed_runs': len(df[df['status'] == 'failed']) if 'failed' in df['status'].values else 0,
        'average_execution_time_minutes': df['execution_time_minutes'].mean(),
        'total_tokens_processed': df['total_tokens'].sum(),
        'average_tokens_per_run': df['total_tokens'].mean(),
        'average_tokens_per_second': df['tokens_per_second'].mean(),
        'total_papers_analyzed': df['papers_analyzed'].sum(),
        'average_report_size_chars': df['report_size_chars'].mean(),
        'average_output_to_input_ratio': df['output_to_input_ratio'].mean()
    }

    # Per-orchestrator statistics
    orchestrator_stats = {}
    for orch in df['orchestrator'].unique():
        orch_df = df[df['orchestrator'] == orch]
        orchestrator_stats[orch] = {
            'runs': len(orch_df),
            'avg_execution_time_minutes': orch_df['execution_time_minutes'].mean(),
            'avg_tokens': orch_df['total_tokens'].mean(),
            'avg_tokens_per_second': orch_df['tokens_per_second'].mean(),
            'total_papers': orch_df['papers_analyzed'].sum(),
            'datasets_tested': orch_df['dataset'].unique().tolist()
        }

    # Per-dataset statistics
    dataset_stats = {}
    for dataset in df['dataset'].unique():
        dataset_df = df[df['dataset'] == dataset]
        dataset_stats[dataset] = {
            'runs': len(dataset_df),
            'orchestrators_tested': dataset_df['orchestrator'].unique().tolist(),
            'avg_execution_time_minutes': dataset_df['execution_time_minutes'].mean(),
            'avg_tokens': dataset_df['total_tokens'].mean(),
            'avg_report_size': dataset_df['report_size_chars'].mean(),
            'papers_per_run': dataset_df['papers_analyzed'].iloc[0] if len(dataset_df) > 0 else 0
        }

    # Agent-level statistics (for Strands)
    agent_stats = {}
    for run in completed_runs:
        if 'agent_details' in run:
            for agent in run['agent_details']:
                agent_name = agent['name']
                if agent_name not in agent_stats:
                    agent_stats[agent_name] = {
                        'runs': 0,
                        'total_tokens': 0,
                        'avg_tokens': 0,
                        'avg_ttft': 0,
                        'ttft_values': []
                    }
                agent_stats[agent_name]['runs'] += 1
                agent_stats[agent_name]['total_tokens'] += agent['tokens']
                agent_stats[agent_name]['ttft_values'].append(agent['ttft'])

    # Calculate agent averages
    for agent_name in agent_stats:
        stats = agent_stats[agent_name]
        stats['avg_tokens'] = stats['total_tokens'] / stats['runs']
        stats['avg_ttft'] = sum(stats['ttft_values']) / len(stats['ttft_values'])
        del stats['ttft_values']  # Remove raw values from final output

    return {
        'summary': summary,
        'orchestrator_stats': orchestrator_stats,
        'dataset_stats': dataset_stats,
        'agent_stats': agent_stats,
        'detailed_runs': completed_runs
    }

def print_formatted_report(stats):
    """Print a nicely formatted report."""

    print("\n" + "="*80)
    print("ORCHESTRATOR RUN ANALYSIS - COMPREHENSIVE REPORT")
    print("="*80)

    # Summary
    print("\n### OVERALL SUMMARY ###")
    summary = stats['summary']
    print(f"Total Runs Analyzed: {summary['total_runs']}")
    print(f"Completed Runs: {summary['completed_runs']}")
    print(f"Average Execution Time: {summary['average_execution_time_minutes']:.2f} minutes")
    print(f"Total Tokens Processed: {summary['total_tokens_processed']:,}")
    print(f"Average Tokens per Run: {summary['average_tokens_per_run']:,.0f}")
    print(f"Average Processing Speed: {summary['average_tokens_per_second']:.2f} tokens/second")
    print(f"Total Papers Analyzed: {summary['total_papers_analyzed']}")
    print(f"Average Report Size: {summary['average_report_size_chars']:,.0f} characters")
    print(f"Average Output/Input Ratio: {summary['average_output_to_input_ratio']:.3f}")

    # Per-Orchestrator Stats
    print("\n### PER-ORCHESTRATOR STATISTICS ###")
    for orch, orch_stats in stats['orchestrator_stats'].items():
        print(f"\n{orch.upper()}:")
        print(f"  Runs: {orch_stats['runs']}")
        print(f"  Datasets Tested: {', '.join(orch_stats['datasets_tested'])}")
        print(f"  Average Execution Time: {orch_stats['avg_execution_time_minutes']:.2f} minutes")
        print(f"  Average Tokens: {orch_stats['avg_tokens']:,.0f}")
        print(f"  Processing Speed: {orch_stats['avg_tokens_per_second']:.2f} tokens/second")
        print(f"  Total Papers Processed: {orch_stats['total_papers']}")

    # Per-Dataset Stats
    print("\n### PER-DATASET STATISTICS ###")
    for dataset, dataset_stats in stats['dataset_stats'].items():
        print(f"\n{dataset.replace('_', ' ').title()}:")
        print(f"  Runs: {dataset_stats['runs']}")
        print(f"  Orchestrators: {', '.join(dataset_stats['orchestrators_tested'])}")
        print(f"  Papers per Run: {dataset_stats['papers_per_run']}")
        print(f"  Average Execution Time: {dataset_stats['avg_execution_time_minutes']:.2f} minutes")
        print(f"  Average Tokens: {dataset_stats['avg_tokens']:,.0f}")
        print(f"  Average Report Size: {dataset_stats['avg_report_size']:,.0f} characters")

    # Agent-Level Stats (Strands)
    if stats['agent_stats']:
        print("\n### AGENT-LEVEL STATISTICS (STRANDS) ###")
        for agent_name, agent_stats in stats['agent_stats'].items():
            print(f"\n{agent_name}:")
            print(f"  Runs: {agent_stats['runs']}")
            print(f"  Average Tokens: {agent_stats['avg_tokens']:,.0f}")
            print(f"  Average Time to First Token: {agent_stats['avg_ttft']:.2f} seconds")
            print(f"  Total Tokens Processed: {agent_stats['total_tokens']:,}")

    # Comparative Analysis
    print("\n### COMPARATIVE ANALYSIS ###")

    # Compare datasets
    theorem_runs = [r for r in completed_runs if r['dataset'] == 'theorem_proving']
    self_imp_runs = [r for r in completed_runs if r['dataset'] == 'self_improvement']

    if theorem_runs and self_imp_runs:
        theorem_avg_tokens = sum(r['total_tokens'] for r in theorem_runs) / len(theorem_runs)
        self_imp_avg_tokens = sum(r['total_tokens'] for r in self_imp_runs) / len(self_imp_runs)

        print(f"\nDataset Token Usage Comparison:")
        print(f"  Theorem Proving: {theorem_avg_tokens:,.0f} avg tokens")
        print(f"  Self-Improvement: {self_imp_avg_tokens:,.0f} avg tokens")
        print(f"  Difference: {abs(self_imp_avg_tokens - theorem_avg_tokens):,.0f} tokens ({((self_imp_avg_tokens/theorem_avg_tokens - 1) * 100):+.1f}%)")

        theorem_avg_time = sum(r['execution_time_minutes'] for r in theorem_runs) / len(theorem_runs)
        self_imp_avg_time = sum(r['execution_time_minutes'] for r in self_imp_runs) / len(self_imp_runs)

        print(f"\nDataset Execution Time Comparison:")
        print(f"  Theorem Proving: {theorem_avg_time:.2f} minutes")
        print(f"  Self-Improvement: {self_imp_avg_time:.2f} minutes")
        print(f"  Difference: {abs(self_imp_avg_time - theorem_avg_time):.2f} minutes ({((self_imp_avg_time/theorem_avg_time - 1) * 100):+.1f}%)")

    # Token distribution across agents
    print("\n### TOKEN DISTRIBUTION ACROSS AGENTS ###")
    for run in completed_runs:
        if 'agent_details' in run:
            print(f"\n{run['dataset'].replace('_', ' ').title()} Run:")
            total = run['total_tokens']
            for agent in run['agent_details']:
                percentage = (agent['tokens'] / total) * 100
                print(f"  {agent['name']}: {agent['tokens']:,} tokens ({percentage:.1f}%)")

def save_to_files(stats):
    """Save statistics to various formats."""

    # Save as JSON
    with open('orchestrator_statistics.json', 'w') as f:
        # Clean up for JSON serialization
        clean_stats = json.loads(json.dumps(stats, default=str))
        json.dump(clean_stats, f, indent=2)
    print("\n✓ Statistics saved to orchestrator_statistics.json")

    # Save detailed runs as CSV
    df = pd.DataFrame(completed_runs)
    # Flatten agent_details for CSV
    df_flat = df.drop('agent_details', axis=1, errors='ignore')
    df_flat.to_csv('orchestrator_runs.csv', index=False)
    print("✓ Run details saved to orchestrator_runs.csv")

    # Create comparison matrix
    comparison_data = []
    for run in completed_runs:
        comparison_data.append({
            'Orchestrator': run['orchestrator'],
            'Dataset': run['dataset'],
            'Time (min)': run['execution_time_minutes'],
            'Tokens': run['total_tokens'],
            'Tokens/sec': run['tokens_per_second'],
            'Report Size': run['report_size_chars'],
            'Output/Input': run['output_to_input_ratio']
        })

    comparison_df = pd.DataFrame(comparison_data)
    comparison_df.to_csv('orchestrator_comparison.csv', index=False)
    print("✓ Comparison matrix saved to orchestrator_comparison.csv")

def main():
    """Main entry point."""
    print("Analyzing orchestrator runs...")

    # Create comprehensive statistics
    stats = create_detailed_statistics()

    # Print formatted report
    print_formatted_report(stats)

    # Save to files
    save_to_files(stats)

    print("\n" + "="*80)
    print("Analysis complete!")
    print("="*80)

if __name__ == "__main__":
    main()