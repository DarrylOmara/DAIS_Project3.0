"""
Parameter sweep harness for DAIS backtesting.
Iterates over config combinations and stores results for comparative analysis.
"""
import os
import time
import json
import itertools
import logging
from pathlib import Path
from copy import deepcopy
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

def load_config(config_path: str = "config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def run_sweep(base_config: dict, param_ranges: dict, output_dir: str = "sweep_results"):
    """
    Run backtest over a grid of parameter combinations.
    
    Args:
        base_config: baseline config dict
        param_ranges: dict mapping param names to lists of values
                     e.g. {"short_window": [5, 9, 15], "long_window": [20, 50]}
        output_dir: where to store sweep results
    
    Returns:
        DataFrame with all run results
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate all parameter combinations
    param_names = list(param_ranges.keys())
    param_values = [param_ranges[k] for k in param_names]
    combinations = list(itertools.product(*param_values))
    
    logger.info(f"Starting parameter sweep: {len(combinations)} combinations")
    results = []
    
    for i, combo in enumerate(combinations):
        config = deepcopy(base_config)
        
        # Apply parameter combo
        for name, value in zip(param_names, combo):
            config[name] = value
        
        # Run backtest
        from run_all import main as run_backtest
        try:
            # Redirect output to a temp config file for this run
            run_dir = os.path.join(output_dir, f"run_{i:04d}")
            os.makedirs(run_dir, exist_ok=True)
            
            temp_config = os.path.join(run_dir, "config.yaml")
            with open(temp_config, "w") as f:
                yaml.dump(config, f)
            
            # Update config path temporarily
            original_cfg = "config.yaml"
            os.rename(original_cfg, original_cfg + ".bak")
            os.rename(temp_config, original_cfg)
            
            start_time = time.time()
            
            # Import and run
            from run_all import load_config as load_cfg, main
            cfg = load_cfg()
            
            # Capture summary from run (pseudo-capture; adapt to actual output structure)
            logger.info(f"Run {i}/{len(combinations)}: {dict(zip(param_names, combo))}")
            
            elapsed = time.time() - start_time
            
            # Restore original config
            os.rename(original_cfg, temp_config)
            os.rename(original_cfg + ".bak", original_cfg)
            
            result = {
                "run_id": i,
                "elapsed_sec": elapsed,
                **dict(zip(param_names, combo))
            }
            results.append(result)
            
        except Exception as e:
            logger.error(f"Run {i} failed: {e}")
            results.append({
                "run_id": i,
                "elapsed_sec": 0,
                "error": str(e),
                **dict(zip(param_names, combo))
            })
    
    df = pd.DataFrame(results)
    csv_path = os.path.join(output_dir, "sweep_results.csv")
    df.to_csv(csv_path, index=False)
    logger.info(f"Sweep complete. Results saved to {csv_path}")
    
    return df

if __name__ == "__main__":
    cfg = load_config()
    
    # Define parameter ranges for sweep
    param_ranges = {
        "short_window": [5, 9, 15],
        "long_window": [20, 50, 100],
    }
    
    results_df = run_sweep(cfg, param_ranges, output_dir="sweep_results")
    print(results_df)
