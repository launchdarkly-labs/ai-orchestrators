#!/usr/bin/env python3
"""
Create line graphs for orchestrator performance across datasets.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Read the CSV data
df = pd.read_csv('orchestrator_all_runs.csv')

# Create friendly dataset names
dataset_names = {
    'emergent_communication': 'Emergent\nCommunication',
    'theorem_proving': 'Theorem\nProving',
    'self_improvement': 'Self\nImprovement'
}

# Order datasets as they appear
dataset_order = ['emergent_communication', 'theorem_proving', 'self_improvement']

# Define colors for each orchestrator
colors = {
    'autogen': '#FF6B6B',      # Red
    'langgraph': '#4ECDC4',    # Teal
    'openai-swarm': '#45B7D1',  # Blue
    'strands': '#96CEB4'       # Green
}

# Create figure with two subplots
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# Graph 1: Cost (Tokens)
for orch in df['orchestrator'].unique():
    orch_data = df[df['orchestrator'] == orch]

    # Get data for each dataset in order
    tokens_data = []
    for dataset in dataset_order:
        dataset_rows = orch_data[orch_data['dataset'] == dataset]
        if not dataset_rows.empty:
            tokens_data.append(dataset_rows['total_tokens'].iloc[0])
        else:
            tokens_data.append(np.nan)

    ax1.plot(range(len(dataset_order)), tokens_data,
             marker='o', label=orch.replace('-', ' ').title(),
             linewidth=2, markersize=8, color=colors[orch])

ax1.set_xlabel('Dataset', fontsize=12)
ax1.set_ylabel('Total Tokens (Cost)', fontsize=12)
ax1.set_title('Token Usage Across Datasets', fontsize=14, fontweight='bold')
ax1.set_xticks(range(len(dataset_order)))
ax1.set_xticklabels([dataset_names[d] for d in dataset_order])
ax1.legend(loc='best')
ax1.grid(True, alpha=0.3)
ax1.set_ylim(bottom=40000, top=120000)

# Graph 2: Speed (Execution Time)
for orch in df['orchestrator'].unique():
    orch_data = df[df['orchestrator'] == orch]

    # Get data for each dataset in order
    time_data = []
    for dataset in dataset_order:
        dataset_rows = orch_data[orch_data['dataset'] == dataset]
        if not dataset_rows.empty:
            time_data.append(dataset_rows['execution_time_minutes'].iloc[0])
        else:
            time_data.append(np.nan)

    ax2.plot(range(len(dataset_order)), time_data,
             marker='o', label=orch.replace('-', ' ').title(),
             linewidth=2, markersize=8, color=colors[orch])

ax2.set_xlabel('Dataset', fontsize=12)
ax2.set_ylabel('Execution Time (minutes)', fontsize=12)
ax2.set_title('Execution Speed Across Datasets', fontsize=14, fontweight='bold')
ax2.set_xticks(range(len(dataset_order)))
ax2.set_xticklabels([dataset_names[d] for d in dataset_order])
ax2.legend(loc='best')
ax2.grid(True, alpha=0.3)
ax2.set_ylim(bottom=0, top=13)

# Adjust layout and save
plt.tight_layout()
plt.savefig('orchestrator_performance_graphs.png', dpi=150, bbox_inches='tight')
plt.show()

print("Graphs saved to orchestrator_performance_graphs.png")

# Also create a summary table
print("\n" + "="*60)
print("PERFORMANCE SUMMARY BY DATASET")
print("="*60)

for dataset in dataset_order:
    print(f"\n{dataset_names[dataset].replace(chr(10), ' ')}:")
    dataset_data = df[df['dataset'] == dataset].sort_values('total_tokens')

    print("\n  Token Efficiency (lowest to highest):")
    for _, row in dataset_data.iterrows():
        print(f"    {row['orchestrator']:15} {row['total_tokens']:,} tokens")

    print("\n  Speed (fastest to slowest):")
    dataset_data_speed = dataset_data.sort_values('execution_time_minutes')
    for _, row in dataset_data_speed.iterrows():
        print(f"    {row['orchestrator']:15} {row['execution_time_minutes']:.2f} minutes")