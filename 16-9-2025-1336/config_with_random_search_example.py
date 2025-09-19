# -*- coding: utf-8 -*-
"""
Example Configuration with Random Search Enabled
Copy the relevant sections to your config.py to enable random search
"""

# =============================================================================
# RANDOM SEARCH EXAMPLE CONFIGURATION
# =============================================================================

# Enable Random Search Hyperparameter Optimization
enable_random_search = True  # Set to True to enable random search
random_search_iterations = 20  # Number of iterations per region (10-50 recommended)
random_search_seed = 42  # Random seed for reproducible results
random_search_scoring_metric = 'overall_accuracy'  # 'overall_accuracy' or 'mean_class_accuracy'

# Hyperparameter Search Ranges
hyperparameter_search_ranges = {
    'numberOfTrees': (50, 500),    # Trees: minimum 50, maximum 500
    'maxNodes': (3, 20),           # Max nodes per tree: minimum 3, maximum 20
    'shrinkage': (0.01, 0.3)       # Learning rate: minimum 0.01, maximum 0.3 (log scale)
}

# Random Search Results Configuration
save_random_search_results = True  # Save detailed results to JSON files
random_search_results_dir = "random_search_results"  # Directory for result files

# =============================================================================
# REQUIRED SETTINGS FOR RANDOM SEARCH
# =============================================================================

# Validation MUST be enabled for random search to work
enable_validation = True  # Required: enables train/validation split
train_validation_split = 0.8  # Recommended: 80% train, 20% validation
validation_seed = 42  # Seed for reproducible validation splits

# =============================================================================
# EXAMPLE CONFIGURATIONS FOR DIFFERENT USE CASES
# =============================================================================

# QUICK TESTING (5-10 minutes per region)
# enable_random_search = True
# random_search_iterations = 10
# hyperparameter_search_ranges = {
#     'numberOfTrees': (50, 200),
#     'maxNodes': (3, 10),
#     'shrinkage': (0.05, 0.2)
# }

# THOROUGH OPTIMIZATION (20-40 minutes per region)  
# enable_random_search = True
# random_search_iterations = 50
# hyperparameter_search_ranges = {
#     'numberOfTrees': (50, 500),
#     'maxNodes': (3, 20),
#     'shrinkage': (0.01, 0.3)
# }

# RESEARCH/EXPERIMENTATION (60+ minutes per region)
# enable_random_search = True
# random_search_iterations = 100
# random_search_scoring_metric = 'mean_class_accuracy'  # Optimize per-class performance
# hyperparameter_search_ranges = {
#     'numberOfTrees': (25, 750),    # Wider range
#     'maxNodes': (2, 25),           # Wider range
#     'shrinkage': (0.005, 0.5)      # Wider range
# }

# =============================================================================
# USAGE INSTRUCTIONS
# =============================================================================

"""
TO ENABLE RANDOM SEARCH:

1. Copy the "RANDOM SEARCH EXAMPLE CONFIGURATION" section above to your config.py

2. Ensure validation is enabled:
   enable_validation = True
   train_validation_split = 0.8

3. Run your normal workflow:
   python3 main.py

4. Random search will run automatically for each region before final training

5. Results will be:
   - Displayed in console output
   - Logged to CONVERSATION_JOURNAL.md
   - Saved as JSON files in random_search_results/ directory

6. Final classifier will use the optimized hyperparameters

EXPECTED OUTPUT:
- Console shows progress for each iteration
- Best hyperparameters displayed after search completes
- Final model trained with optimized parameters
- Validation performance metrics shown for optimized model
"""