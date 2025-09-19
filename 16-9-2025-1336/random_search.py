# -*- coding: utf-8 -*-
"""
Random Search Hyperparameter Optimization for Crop Classifier
Implements random search for XGBoost hyperparameters: numberOfTrees, maxNodes, shrinkage
"""

import random
import time
from datetime import datetime, timedelta, timezone
import json
import math
import crop_functions as cf


class RandomSearchOptimizer:
    """
    Random Search optimizer for XGBoost hyperparameters in crop classification
    
    Optimizes:
    - numberOfTrees: Number of trees in XGBoost ensemble
    - maxNodes: Maximum number of nodes per tree
    - shrinkage: Learning rate/shrinkage parameter
    """
    
    def __init__(self, search_ranges, n_iterations=10, random_seed=42, scoring_metric='overall_accuracy'):
        """
        Initialize random search optimizer
        
        Args:
            search_ranges: Dict with hyperparameter ranges
            n_iterations: Number of random search iterations
            random_seed: Random seed for reproducibility
            scoring_metric: Metric to optimize ('overall_accuracy', 'mean_class_accuracy')
        """
        self.search_ranges = search_ranges
        self.n_iterations = n_iterations
        self.random_seed = random_seed
        self.scoring_metric = scoring_metric
        self.search_history = []
        self.best_params = None
        self.best_score = -float('inf')
        
        # Set random seed for reproducibility
        random.seed(random_seed)
    
    def sample_hyperparameters(self):
        """
        Sample random hyperparameters from defined ranges
        
        Returns:
            dict: Sampled hyperparameters
        """
        params = {}
        
        # Sample numberOfTrees (integer)
        if 'numberOfTrees' in self.search_ranges:
            min_trees, max_trees = self.search_ranges['numberOfTrees']
            params['numberOfTrees'] = random.randint(min_trees, max_trees)
        
        # Sample maxNodes (integer)  
        if 'maxNodes' in self.search_ranges:
            min_nodes, max_nodes = self.search_ranges['maxNodes']
            params['maxNodes'] = random.randint(min_nodes, max_nodes)
            
        # Sample shrinkage (float, log scale for better sampling)
        if 'shrinkage' in self.search_ranges:
            min_shrink, max_shrink = self.search_ranges['shrinkage']
            # Sample on log scale for better exploration of learning rates
            log_min = math.log10(min_shrink)
            log_max = math.log10(max_shrink)
            log_shrink = random.uniform(log_min, log_max)
            params['shrinkage'] = round(10**log_shrink, 4)
        
        return params
    
    def evaluate_hyperparameters(self, params, training_points, train_stack, validation_points, cdl_classes):
        """
        Evaluate a set of hyperparameters using validation data
        
        Args:
            params: Dictionary of hyperparameters to evaluate
            training_points: Training data points
            train_stack: Training feature stack
            validation_points: Validation data points
            cdl_classes: Crop class definitions
            
        Returns:
            float: Validation score for the hyperparameters
        """
        try:
            # Train classifier with current hyperparameters
            classifier = cf.train_classifier(
                training_points, 
                train_stack, 
                params['numberOfTrees'], 
                params['maxNodes'], 
                params['shrinkage']
            )
            
            # Evaluate on validation set
            validation_metrics = cf.evaluate_validation_performance(
                classifier, validation_points, train_stack, cdl_classes
            )
            
            # Extract scoring metric
            if self.scoring_metric == 'overall_accuracy':
                score = validation_metrics['overall_accuracy']
            elif self.scoring_metric == 'mean_class_accuracy':
                # Calculate mean per-class accuracy
                class_accuracies = [acc for acc in validation_metrics['class_accuracy'].values() 
                                  if not math.isnan(acc)]
                score = sum(class_accuracies) / len(class_accuracies) if class_accuracies else 0
            else:
                score = validation_metrics['overall_accuracy']  # Default fallback
            
            return score, validation_metrics
            
        except Exception as e:
            print(f"   ❌ Error evaluating hyperparameters {params}: {e}")
            return 0.0, None
    
    def run_search(self, training_points, train_stack, validation_points, cdl_classes, region_name="Unknown"):
        """
        Run random search optimization
        
        Args:
            training_points: Training data points
            train_stack: Training feature stack  
            validation_points: Validation data points
            cdl_classes: Crop class definitions
            region_name: Name of region being processed
            
        Returns:
            dict: Best hyperparameters found
        """
        print(f"\n🔍 STARTING RANDOM SEARCH OPTIMIZATION for {region_name}")
        print("="*60)
        print(f"Search Configuration:")
        print(f"   Iterations: {self.n_iterations}")
        print(f"   Scoring Metric: {self.scoring_metric}")
        print(f"   Search Ranges: {self.search_ranges}")
        print(f"   Random Seed: {self.random_seed}")
        print("="*60)
        
        search_start_time = time.time()
        
        for iteration in range(self.n_iterations):
            iteration_start = time.time()
            
            # Sample random hyperparameters
            params = self.sample_hyperparameters()
            
            print(f"\n🔄 Iteration {iteration + 1}/{self.n_iterations}")
            print(f"   Testing: {params}")
            
            # Evaluate hyperparameters
            score, validation_metrics = self.evaluate_hyperparameters(
                params, training_points, train_stack, validation_points, cdl_classes
            )
            
            iteration_time = time.time() - iteration_start
            
            # Store results
            result = {
                'iteration': iteration + 1,
                'params': params.copy(),
                'score': score,
                'validation_metrics': validation_metrics,
                'evaluation_time': iteration_time,
                'timestamp': datetime.now().isoformat()
            }
            self.search_history.append(result)
            
            # Update best parameters
            if score > self.best_score:
                self.best_score = score
                self.best_params = params.copy()
                print(f"   ✅ NEW BEST: Score={score:.4f} ({score*100:.2f}%) - {params}")
            else:
                print(f"   📊 Score={score:.4f} ({score*100:.2f}%)")
            
            print(f"   ⏱️  Iteration time: {iteration_time:.1f}s")
        
        search_duration = time.time() - search_start_time
        
        # Print final results
        print(f"\n{'='*60}")
        print(f"🎯 RANDOM SEARCH COMPLETED for {region_name}")
        print(f"{'='*60}")
        print(f"Total Search Time: {search_duration:.1f}s ({search_duration/60:.1f} minutes)")
        print(f"Best Score: {self.best_score:.4f} ({self.best_score*100:.2f}%)")
        print(f"Best Parameters: {self.best_params}")
        print(f"Improvement over baseline: {self._calculate_improvement():.2f}%")
        
        # Log results to journal
        self._log_search_results(region_name, search_duration)
        
        return self.best_params
    
    def _calculate_improvement(self):
        """Calculate improvement over baseline (first iteration or default params)"""
        if len(self.search_history) == 0:
            return 0.0
        
        baseline_score = self.search_history[0]['score']  # First iteration as baseline
        if baseline_score == 0:
            return 0.0
        
        improvement = ((self.best_score - baseline_score) / baseline_score) * 100
        return improvement
    
    def _log_search_results(self, region_name, search_duration):
        """Log random search results to conversation journal"""
        try:
            # Get current time in local timezone (UTC+3 based on user preference)
            utc_time = datetime.now(timezone.utc)
            local_time = utc_time + timedelta(hours=3)
            timestamp = local_time.strftime('%Y-%m-%d %H:%M:%S')
            
            log_entry = f"""
## Random Search Hyperparameter Optimization - {region_name}
**Date:** {timestamp} (Local Time)
**Search Duration:** {search_duration:.1f}s ({search_duration/60:.1f} minutes)

### Search Configuration
- **Iterations:** {self.n_iterations}
- **Scoring Metric:** {self.scoring_metric}
- **Random Seed:** {self.random_seed}
- **Search Ranges:**
  - numberOfTrees: {self.search_ranges.get('numberOfTrees', 'Not specified')}
  - maxNodes: {self.search_ranges.get('maxNodes', 'Not specified')}
  - shrinkage: {self.search_ranges.get('shrinkage', 'Not specified')}

### Best Results
- **Best Score:** {self.best_score:.4f} ({self.best_score*100:.2f}%)
- **Best Parameters:**
  - numberOfTrees: {self.best_params.get('numberOfTrees', 'N/A')}
  - maxNodes: {self.best_params.get('maxNodes', 'N/A')}
  - shrinkage: {self.best_params.get('shrinkage', 'N/A')}
- **Improvement over baseline:** {self._calculate_improvement():.2f}%

### Search History Summary
| Iteration | numberOfTrees | maxNodes | shrinkage | Score | Time (s) |
|-----------|---------------|----------|-----------|-------|----------|
"""
            
            # Add search history table
            for result in self.search_history:
                params = result['params']
                log_entry += f"| {result['iteration']} | {params.get('numberOfTrees', 'N/A')} | {params.get('maxNodes', 'N/A')} | {params.get('shrinkage', 'N/A')} | {result['score']:.4f} | {result['evaluation_time']:.1f} |\n"
            
            log_entry += "\n---\n"
            
            # Write to journal
            with open("CONVERSATION_JOURNAL.md", 'a', encoding='utf-8') as f:
                f.write(log_entry)
                
        except Exception as e:
            print(f"⚠️  Could not log random search results to journal: {e}")
    
    def get_search_summary(self):
        """Get summary of search results"""
        if not self.search_history:
            return None
        
        scores = [result['score'] for result in self.search_history]
        times = [result['evaluation_time'] for result in self.search_history]
        
        # Calculate statistics using standard Python functions
        mean_score = sum(scores) / len(scores) if scores else 0
        mean_time = sum(times) / len(times) if times else 0
        
        # Calculate standard deviation manually
        if len(scores) > 1:
            variance = sum((x - mean_score) ** 2 for x in scores) / (len(scores) - 1)
            std_score = math.sqrt(variance)
        else:
            std_score = 0
        
        summary = {
            'best_params': self.best_params,
            'best_score': self.best_score,
            'n_iterations': len(self.search_history),
            'score_stats': {
                'mean': mean_score,
                'std': std_score,
                'min': min(scores) if scores else 0,
                'max': max(scores) if scores else 0
            },
            'time_stats': {
                'total_time': sum(times),
                'mean_time': mean_time,
                'total_time_minutes': sum(times) / 60
            },
            'improvement_pct': self._calculate_improvement()
        }
        
        return summary
    
    def save_results(self, filepath):
        """Save search results to JSON file"""
        try:
            results_data = {
                'search_config': {
                    'search_ranges': self.search_ranges,
                    'n_iterations': self.n_iterations,
                    'random_seed': self.random_seed,
                    'scoring_metric': self.scoring_metric
                },
                'best_params': self.best_params,
                'best_score': self.best_score,
                'search_history': self.search_history,
                'summary': self.get_search_summary()
            }
            
            with open(filepath, 'w') as f:
                json.dump(results_data, f, indent=2, default=str)
            
            print(f"Random search results saved to: {filepath}")
            
        except Exception as e:
            print(f"⚠️  Could not save results to {filepath}: {e}")


def create_default_search_ranges():
    """Create default search ranges for hyperparameters"""
    return {
        'numberOfTrees': (50, 500),    # Trees: 50 to 500
        'maxNodes': (3, 20),           # Max nodes: 3 to 20  
        'shrinkage': (0.01, 0.3)       # Learning rate: 0.01 to 0.3
    }


def run_random_search_for_region(training_points, train_stack, validation_points, cdl_classes, 
                                region_name, search_config):
    """
    Convenience function to run random search for a specific region
    
    Args:
        training_points: Training data points
        train_stack: Training feature stack
        validation_points: Validation data points  
        cdl_classes: Crop class definitions
        region_name: Name of region being processed
        search_config: Dictionary with search configuration
        
    Returns:
        dict: Best hyperparameters found
    """
    optimizer = RandomSearchOptimizer(
        search_ranges=search_config.get('search_ranges', create_default_search_ranges()),
        n_iterations=search_config.get('n_iterations', 10),
        random_seed=search_config.get('random_seed', 42),
        scoring_metric=search_config.get('scoring_metric', 'overall_accuracy')
    )
    
    best_params = optimizer.run_search(
        training_points, train_stack, validation_points, cdl_classes, region_name
    )
    
    # Save results if filepath provided
    if 'results_filepath' in search_config:
        optimizer.save_results(search_config['results_filepath'])
    
    return best_params, optimizer.get_search_summary()