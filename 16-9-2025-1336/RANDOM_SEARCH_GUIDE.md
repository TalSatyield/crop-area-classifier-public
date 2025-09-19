# Random Search Hyperparameter Optimization Guide

## Overview

This implementation adds random search hyperparameter optimization to the crop classification system. Random search automatically finds optimal XGBoost hyperparameters by testing random combinations within specified ranges and selecting the best performing set based on validation metrics.

## Hyperparameters Optimized

The system optimizes three key XGBoost hyperparameters:

1. **numberOfTrees** (50-500): Number of trees in the XGBoost ensemble
2. **maxNodes** (3-20): Maximum number of nodes per tree
3. **shrinkage** (0.01-0.3): Learning rate/shrinkage parameter (sampled on log scale)

## Configuration

### Enable Random Search

To enable random search, modify `config.py`:

```python
# Random Search Hyperparameter Optimization Parameters
enable_random_search = True  # Enable random search hyperparameter optimization
random_search_iterations = 20  # Number of random search iterations per region
random_search_seed = 42  # Random seed for reproducible hyperparameter sampling
random_search_scoring_metric = 'overall_accuracy'  # Metric to optimize
```

### Search Ranges

Customize hyperparameter search ranges in `config.py`:

```python
# Hyperparameter Search Ranges
hyperparameter_search_ranges = {
    'numberOfTrees': (50, 500),    # Trees: minimum 50, maximum 500
    'maxNodes': (3, 20),           # Max nodes per tree: minimum 3, maximum 20
    'shrinkage': (0.01, 0.3)       # Learning rate: minimum 0.01, maximum 0.3
}
```

### Results Configuration

Control result saving:

```python
# Random Search Results
save_random_search_results = True  # Save detailed random search results to JSON files
random_search_results_dir = "random_search_results"  # Directory to save results
```

## How It Works

### 1. Workflow Integration

Random search is integrated into the main workflow:

1. **Training Data Split**: Creates train/validation split (required for optimization)
2. **Random Search**: Tests multiple hyperparameter combinations
3. **Best Parameters**: Selects hyperparameters with highest validation score
4. **Final Training**: Trains final classifier with optimized hyperparameters
5. **Prediction**: Uses optimized model for crop area prediction

### 2. Hyperparameter Sampling

- **numberOfTrees**: Uniform random integers within range
- **maxNodes**: Uniform random integers within range  
- **shrinkage**: Log-scale sampling for better exploration of learning rates

### 3. Evaluation Metrics

Two scoring metrics available:

- **overall_accuracy**: Overall validation accuracy (default)
- **mean_class_accuracy**: Average per-class accuracy

### 4. Per-Region Optimization

Random search runs independently for each state/region, allowing:
- Region-specific optimal hyperparameters
- Parallel processing across regions
- Detailed per-region performance tracking

## Usage Examples

### Basic Usage

```python
# In config.py
enable_random_search = True
random_search_iterations = 10  # Quick test

# Run main.py - random search will run automatically
python3 main.py
```

### Advanced Configuration

```python
# In config.py
enable_random_search = True
random_search_iterations = 50  # More thorough search
random_search_scoring_metric = 'mean_class_accuracy'  # Optimize per-class accuracy

# Custom search ranges
hyperparameter_search_ranges = {
    'numberOfTrees': (100, 400),   # Focus on higher tree counts
    'maxNodes': (5, 15),           # Mid-range node counts
    'shrinkage': (0.05, 0.2)       # Conservative learning rates
}
```

## Output and Results

### Console Output

Random search provides detailed progress information:

```
🔍 RANDOM SEARCH OPTIMIZATION for Illinois
============================================================
Search Configuration:
   Iterations: 20
   Scoring Metric: overall_accuracy
   Search Ranges: {'numberOfTrees': (50, 500), 'maxNodes': (3, 20), 'shrinkage': (0.01, 0.3)}
   Random Seed: 42

🔄 Iteration 1/20
   Testing: {'numberOfTrees': 234, 'maxNodes': 12, 'shrinkage': 0.0847}
   📊 Score=0.8756 (87.56%)
   ⏱️  Iteration time: 45.2s

🔄 Iteration 2/20
   Testing: {'numberOfTrees': 156, 'maxNodes': 8, 'shrinkage': 0.1234}
   ✅ NEW BEST: Score=0.8923 (89.23%) - {'numberOfTrees': 156, 'maxNodes': 8, 'shrinkage': 0.1234}
   ⏱️  Iteration time: 38.7s

...

============================================================
🎯 RANDOM SEARCH COMPLETED for Illinois
============================================================
Total Search Time: 847.3s (14.1 minutes)
Best Score: 0.8923 (89.23%)
Best Parameters: {'numberOfTrees': 156, 'maxNodes': 8, 'shrinkage': 0.1234}
Improvement over baseline: 3.45%

🎯 Training final classifier with OPTIMIZED hyperparameters:
   numberOfTrees: 156
   maxNodes: 8
   shrinkage: 0.1234
```

### Journal Logging

Detailed results are logged to `CONVERSATION_JOURNAL.md`:

```markdown
## Random Search Hyperparameter Optimization - Illinois
**Date:** 2025-09-19 14:23:45 (Local Time)
**Search Duration:** 847.3s (14.1 minutes)

### Search Configuration
- **Iterations:** 20
- **Scoring Metric:** overall_accuracy
- **Random Seed:** 42
- **Search Ranges:**
  - numberOfTrees: (50, 500)
  - maxNodes: (3, 20)
  - shrinkage: (0.01, 0.3)

### Best Results
- **Best Score:** 0.8923 (89.23%)
- **Best Parameters:**
  - numberOfTrees: 156
  - maxNodes: 8
  - shrinkage: 0.1234
- **Improvement over baseline:** 3.45%

### Search History Summary
| Iteration | numberOfTrees | maxNodes | shrinkage | Score | Time (s) |
|-----------|---------------|----------|-----------|-------|----------|
| 1 | 234 | 12 | 0.0847 | 0.8756 | 45.2 |
| 2 | 156 | 8 | 0.1234 | 0.8923 | 38.7 |
...
```

### JSON Results Files

Detailed results saved to `random_search_results/` directory:

```json
{
  "search_config": {
    "search_ranges": {"numberOfTrees": [50, 500], "maxNodes": [3, 20], "shrinkage": [0.01, 0.3]},
    "n_iterations": 20,
    "random_seed": 42,
    "scoring_metric": "overall_accuracy"
  },
  "best_params": {"numberOfTrees": 156, "maxNodes": 8, "shrinkage": 0.1234},
  "best_score": 0.8923,
  "search_history": [...],
  "summary": {
    "improvement_pct": 3.45,
    "score_stats": {"mean": 0.8654, "std": 0.0234, "min": 0.8234, "max": 0.8923},
    "time_stats": {"total_time": 847.3, "mean_time": 42.4, "total_time_minutes": 14.1}
  }
}
```

## Performance Considerations

### Computational Cost

- Each iteration requires training a full XGBoost model
- Total time = iterations × average_training_time_per_model
- Typical range: 10-50 iterations (5-60 minutes per region)

### Recommendations

- **Development**: 5-10 iterations for quick testing
- **Production**: 20-50 iterations for thorough optimization
- **Research**: 50-100 iterations for comprehensive search

### Memory Usage

- Random search uses same memory as regular training
- Validation split reduces training data size slightly
- No significant additional memory overhead

## Prerequisites

### Required Settings

Random search requires:

```python
enable_validation = True  # Must be enabled for validation-based optimization
train_validation_split = 0.8  # Recommended 80% train, 20% validation
```

### Error Handling

If validation is disabled:
```
⚠️  Random search disabled: requires validation split (enable_validation=True)
```

## Best Practices

### 1. Search Range Selection

- **numberOfTrees**: Start with (50, 500), adjust based on computational budget
- **maxNodes**: Use (3, 20) for good bias-variance tradeoff
- **shrinkage**: Keep (0.01, 0.3) for stable learning rates

### 2. Iteration Count

- **Quick test**: 5-10 iterations
- **Standard optimization**: 20-30 iterations  
- **Thorough search**: 50+ iterations

### 3. Reproducibility

- Set `random_search_seed` for reproducible results
- Use same seed across experiments for fair comparison

### 4. Monitoring

- Monitor console output for convergence patterns
- Check if best score improves in later iterations
- Adjust iteration count based on improvement trends

## Troubleshooting

### Common Issues

1. **No improvement found**
   - Increase iteration count
   - Widen search ranges
   - Check validation data quality

2. **Long runtime**
   - Reduce iteration count
   - Narrow search ranges
   - Use smaller validation split

3. **Memory errors**
   - Reduce `maxNodes` upper bound
   - Decrease validation split size
   - Process fewer states simultaneously

### Validation

Run the test suite to verify installation:

```bash
python3 test_random_search_simple.py
```

## Integration Status

✅ **Complete Implementation**
- Random search module (`random_search.py`)
- Configuration parameters (`config.py`)
- Main workflow integration (`main.py`)
- Comprehensive logging and result saving
- Validation and testing suite

The random search implementation is production-ready and integrated into the existing crop classification workflow.