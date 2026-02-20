
import json
import matplotlib.pyplot as plt
import sys
import os
import statistics

def plot_hist(data, title, xlabel, filename, color):
    if not data:
        return
        
    mean_val = statistics.mean(data)
    median_val = statistics.median(data)
    
    plt.figure(figsize=(10, 6))
    plt.hist(data, bins=30, color=color, edgecolor='black')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel('Count')
    plt.grid(True, alpha=0.3)
    
    # Add annotations
    stats_text = f"Mean: {mean_val:.2f}\nMedian: {median_val:.2f}\nMin: {min(data):.2f}\nMax: {max(data):.2f}"
    plt.annotate(stats_text, xy=(0.95, 0.95), xycoords='axes fraction', 
                 fontsize=12, horizontalalignment='right', verticalalignment='top',
                 bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.8))
                 
    plt.savefig(filename)
    print(f"Saved {filename}")
    plt.close()

def plot_results():
    input_file = "benchmark/results/llm_tool_metrics.json"
    output_prefix = "benchmark/results/llm_tool"
    
    print(f"Reading from {input_file}...")
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
        
    execution_times = [r['duration_ms'] for r in results]
    output_tokens = [r['estimated_tokens'] for r in results]
    input_tokens = [r.get('input_sql_tokens', 0) for r in results]
    
    # Filter for non-zero (or strictly valid=False)
    # error_tokens and issue_sql_tokens are now in a separate file
    error_stats_file = str(input_file).replace('.json', '_error_stats.json')
    error_tokens = []
    issue_sql_tokens = []
    
    if os.path.exists(error_stats_file):
        with open(error_stats_file, 'r', encoding='utf-8') as f:
            error_results = json.load(f)
            error_tokens = [r.get('error_tokens', 0) for r in error_results]
            issue_sql_tokens = [r.get('issue_sql_tokens', 0) for r in error_results]
        print(f"Loaded {len(error_results)} error records.")
    
    print(f"Loaded {len(results)} records.")
    
    # Time Distribution
    plot_hist(execution_times, 'Distribution of Query Execution Times', 'Time (ms)', 
              f"{output_prefix}_time_dist.png", 'skyblue')
              
    # Output Token Distribution (AST)
    plot_hist(output_tokens, 'Distribution of AST Output Token Counts', 'Tokens', 
              f"{output_prefix}_token_dist.png", 'lightgreen')

    # Input Token Distribution
    plot_hist(input_tokens, 'Distribution of Input SQL Token Counts (All)', 'Tokens',
              f"{output_prefix}_input_token_dist.png", 'salmon')

    # Error Token Distribution
    # Error Token Distribution
    # Filter out empty/trivial errors
    # If error_tokens is <= 2 (likely just special tokens) or very small, ignore it if message is trivial
    # For plotting, just filter > 5 for safety, or inspect if we have the message content.
    # But since we only have counts here, let's look at the JSON if possible, but simpler: filter > 2.
    error_tokens = [t for t in error_tokens if t > 2]
    
    plot_hist(error_tokens, 'Distribution of Error Token Counts (Invalid Queries)', 'Tokens',
              f"{output_prefix}_error_token_dist.png", 'crimson')
              
    # Also save to requested path
    try:
        plot_hist(error_tokens, 'Distribution of Error Token Counts (Invalid Queries)', 'Tokens',
                  r"C:\Users\smeet\Downloads\dist.png", 'crimson')
        print(r"Saved C:\Users\smeet\Downloads\dist.png")
    except Exception as e:
        print(f"Could not save to Downloads: {e}")
              
    # Invalid SQL Token Distribution
    issue_sql_tokens = [t for t in issue_sql_tokens if t > 0]
    plot_hist(issue_sql_tokens, 'Distribution of Issue SQL Token Counts (Invalid Queries)', 'Tokens',
              f"{output_prefix}_issue_sql_token_dist.png", 'orange')

if __name__ == "__main__":
    try:
        plot_results()
        print("Done.")
    except Exception as e:
        print(f"An error occurred: {e}")
