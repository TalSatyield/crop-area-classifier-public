# -*- coding: utf-8 -*-
"""
Main script for Corn and Soy Area Classification in USA
Revised version with separated config and functions
"""

import ee
import time
from datetime import datetime, timedelta, timezone
import os
import config
import crop_functions as cf
from usda_data import (USDA_CORN_PLANTED_ACRES, USDA_SOY_PLANTED_ACRES, 
                       USDA_WHEAT_PLANTED_ACRES, USDA_COTTON_PLANTED_ACRES, 
                       USDA_RICE_PLANTED_ACRES, USDA_SORGHUM_PLANTED_ACRES,
                       USDA_HAY_PLANTED_ACRES, USDA_SPRING_WHEAT_PLANTED_ACRES,
                       USDA_WINTER_WHEAT_PLANTED_ACRES)
import random_search


def get_local_time():
    """Get current time in local timezone (assuming UTC+3 based on user input)"""
    utc_time = datetime.now(timezone.utc)
    local_time = utc_time + timedelta(hours=3)  # UTC+3 timezone
    return local_time


def print_detailed_results_table(state_results, error_results, processing_duration_str, 
                                Final_corn_area, Final_soy_area, inference_year, usda_data_dict):
    """Print detailed per-state results table matching specified format"""
    
    # Print per-state results
    for state_name in sorted(state_results.keys()):
        print(f"\n📍 {state_name}:")
        
        # Get state results
        state_data = state_results[state_name]
        
        # Print CORN results
        corn_pred = state_data.get('Corn', 0)
        corn_usda = None
        if 'Corn' in usda_data_dict and state_name in usda_data_dict['Corn']:
            corn_usda = usda_data_dict['Corn'][state_name].get(inference_year, None)
        
        if corn_usda is not None:
            corn_error = ((corn_pred - corn_usda) / corn_usda * 100) if corn_usda != 0 else 0
            if corn_usda >= 1000:  # Handle very large values like Kansas USDA data error
                corn_usda_str = f"{corn_usda:>4.0f}M"
            else:
                corn_usda_str = f"{corn_usda:>4.1f}M" if corn_usda >= 0.1 else f"{corn_usda:>4.2f}M"
            error_str = f"{corn_error:+5.1f}%"
        else:
            corn_usda_str = " N/AM"
            error_str = "No data"
        
        print(f"     CORN: Pred={corn_pred:5.2f}M | USDA={corn_usda_str} | Error={error_str}")
        
        # Print SOY results
        soy_pred = state_data.get('Soy', 0)
        soy_usda = None
        if 'Soy' in usda_data_dict and state_name in usda_data_dict['Soy']:
            soy_usda = usda_data_dict['Soy'][state_name].get(inference_year, None)
        
        if soy_usda is not None:
            soy_error = ((soy_pred - soy_usda) / soy_usda * 100) if soy_usda != 0 else 0
            soy_usda_str = f"{soy_usda:>4.1f}M" if soy_usda >= 0.1 else f"{soy_usda:>4.2f}M"
            error_str = f"{soy_error:+5.1f}%"
        else:
            soy_usda_str = " N/AM"
            error_str = "No data"
        
        print(f"      SOY: Pred={soy_pred:5.2f}M | USDA={soy_usda_str} | Error={error_str}")
        
        # Add region_name for next state (matching the format in your example)
        state_list = sorted(list(state_results.keys()))
        current_index = state_list.index(state_name)
        if current_index < len(state_list) - 1:
            next_state = state_list[current_index + 1]
            print(f"region_name: {next_state}")
    
    # Add timing information
    print(f"\n⏱️  State Processing Completed in: {processing_duration_str}")
    print("="*60)
    
    # Add totals
    print(f"total_FINAL corn_area all USA (million acres): {Final_corn_area}")
    print(f"total_FINAL soy_area all USA (million acres): {Final_soy_area}")
    print()
    print("="*60)
    print("🎯 FINAL RESULTS:")
    print(f"Corn Area (million acres): {Final_corn_area}")
    print(f"Soy Area (million acres): {Final_soy_area}")
    print("="*60)


def print_simplified_error_summary(error_results, year):
    """Print simplified error summary showing only key metrics for selected crops"""
    print(f"\n📊 VALIDATION vs USDA DATA ({year}):")
    print("-" * 50)
    
    # Overall statistics for all processed crops
    crops_processed = list(error_results['overall'].keys())
    for crop in crops_processed:
        overall = error_results['overall'][crop]
        crop_name = crop.upper()
        
        if 'total_error_pct' in overall:
            predicted = overall['total_predicted']
            usda = overall['total_usda']
            error_pct = overall['total_error_pct']
            
            print(f"{crop_name:>6}: Predicted={predicted:6.1f}M acres | USDA={usda:6.1f}M acres | Error={error_pct:+5.1f}%")
        else:
            print(f"{crop_name:>6}: No USDA data available")
    
    print("-" * 50)


def Calculate_Corn_Soy_Area_USA(total_corn_area=0, total_soy_area=0, state_results=None):
    """
    Main function to calculate corn and soy areas for USA states
    
    Args:
        total_corn_area: Running total of corn area (for retry runs)
        total_soy_area: Running total of soy area (for retry runs)
        state_results: Dictionary to store per-state results for error analysis
    
    Returns:
        tuple: (Final_corn_area, Final_soy_area, total_corn_area, total_soy_area, failed_states, state_results, classification_data)
    """
    # Track processing time
    processing_start = time.time()
    
    # Get calculated parameters
    calc_params = config.get_calculated_parameters()
    states_to_use = calc_params['states_to_use']
    exterpolation_factor_corn = calc_params['exterpolation_factor_corn']
    exterpolation_factor_soy = calc_params['exterpolation_factor_soy']
    training_year = calc_params['training_year']
    inference_year = calc_params['inference_year']
    
    failed_states = []  # list of failed states. trying to run again later
    classification_data = {}  # Store classification images and geometries for export
    
    # Initialize state_results dictionary if not provided
    if state_results is None:
        state_results = {}

    for region_name in states_to_use:
        print('region_name:', region_name)
        try:
            # Setup region geometry
            roi = ee.FeatureCollection("TIGER/2018/States").filter(ee.Filter.eq("NAME", region_name))
            aoi = roi.geometry()
            aoi_convexHull = aoi.convexHull()
            aoi_fc = ee.FeatureCollection(aoi)

            # ------------------------ Prepare Training Data ------------------------
            historical_mask = cf.get_historical_crop_mask(
                aoi, 
                training_year - config.n_years_rotation_history, 
                training_year, 
                config.cdl_classes
            )
            
            years_range_prev = list(range(
                training_year - config.n_years_rotation_history, 
                training_year
            ))
            
            # Load CDL with confidence data if filtering is enabled
            if config.enable_cdl_confidence_filtering:
                print(f"   📊 Loading CDL {training_year} with confidence band...")
                
                # First check if confidence band is available for this year
                cdl_temp = ee.ImageCollection("USDA/NASS/CDL").filter(ee.Filter.calendarRange(training_year, training_year, "year")).first()
                available_bands = cdl_temp.bandNames().getInfo()
                
                if 'confidence' in available_bands:
                    # Confidence band available - proceed with filtering
                    print(f"   ✅ CDL {training_year} has confidence band - applying filtering")
                    cdl_with_confidence = cf.load_cdl(training_year, historical_mask, aoi_convexHull, include_confidence=True)
                    cdl_filtered = cf.apply_confidence_mask(cdl_with_confidence, config.cdl_confidence_threshold)
                    cf.log_confidence_metrics_to_journal(training_year, config.cdl_confidence_threshold, region_name)
                    cdl_previous_year = cdl_filtered.select(f"CDL_{training_year}")
                else:
                    # No confidence band - skip filtering
                    print(f"   ⚠️  CDL {training_year} has no confidence band - skipping confidence filtering")
                    cdl_previous_year = cf.load_cdl(training_year, historical_mask, aoi_convexHull)
            else:
                print(f"   📊 Loading CDL {training_year} (no confidence filtering)...")
                cdl_previous_year = cf.load_cdl(training_year, historical_mask, aoi_convexHull)
            
            label_previous_year = cf.encode_label(cdl_previous_year, config.cdl_classes)
            train_stack = cf.add_rotation_features(years_range_prev, historical_mask, config.cdl_classes, aoi_convexHull)

            # Add satellite features if requested
            if config.use_satellite_data == 1:
                date_start = f"{training_year}-{config.month_start}-{config.day_start}"
                date_end = f"{training_year}-{config.month_end}-{config.day_end}"
                
                s2 = cf.get_s2_sr_cld_col(aoi_convexHull, date_start, date_end, config.QA_BAND, config.CLEAR_THRESHOLD)
                filtered_collection = cf.process_satellite_data(s2, config.features_to_use, historical_mask)
                quality_mosaic_img = filtered_collection.qualityMosaic(config.quality_mosaic_band)
                train_stack = train_stack.addBands(quality_mosaic_img)

            training_image = train_stack.addBands(label_previous_year)

            # Create training points - dynamic based on number of classes
            num_classes = len(config.cdl_classes)  # Includes "Other" + selected crops
            if config.use_satellite_data == 1:
                classPoints = [config.n_points_per_class_satellite] * num_classes
            else:
                classPoints = [config.n_points_per_class_no_satellite] * num_classes
                
            training_points = cf.create_training_points(
                training_image, aoi_fc, aoi_convexHull, config.cdl_classes, 
                classPoints, config.resolution, config.county_scale_reduction_factor
            )

            # ------------------------ Train/Validation Split ------------------------
            if config.enable_validation:
                print(f"🔄 Splitting training data: {config.train_validation_split:.1%} train, {1-config.train_validation_split:.1%} validation")
                train_points, validation_points = cf.split_training_points(
                    training_points, config.train_validation_split, config.validation_seed
                )
                
                # ------------------------ Random Search Optimization ------------------------
                optimized_params = None
                if config.enable_random_search:
                    print(f"\n🔍 RANDOM SEARCH HYPERPARAMETER OPTIMIZATION ENABLED")
                    print("="*60)
                    
                    # Create results directory if needed
                    if config.save_random_search_results:
                        os.makedirs(config.random_search_results_dir, exist_ok=True)
                        results_filepath = os.path.join(
                            config.random_search_results_dir, 
                            f"random_search_{region_name.replace(' ', '_')}_{training_year}_{get_local_time().strftime('%Y%m%d_%H%M%S')}.json"
                        )
                    else:
                        results_filepath = None
                    
                    # Configure random search
                    search_config = {
                        'search_ranges': config.hyperparameter_search_ranges,
                        'n_iterations': config.random_search_iterations,
                        'random_seed': config.random_search_seed,
                        'scoring_metric': config.random_search_scoring_metric,
                        'results_filepath': results_filepath
                    }
                    
                    # Run random search optimization
                    optimized_params, search_summary = random_search.run_random_search_for_region(
                        train_points, train_stack, validation_points, config.cdl_classes,
                        region_name, search_config
                    )
                    
                    print(f"\n✅ Random search completed!")
                    print(f"   Best hyperparameters: {optimized_params}")
                    print(f"   Improvement: {search_summary['improvement_pct']:.2f}%")
                    print("="*60)
                
                # Use optimized parameters if available, otherwise use config defaults
                if optimized_params:
                    num_trees = optimized_params['numberOfTrees']
                    max_nodes = optimized_params['maxNodes']
                    shrinkage_param = optimized_params['shrinkage']
                    print(f"🎯 Training final classifier with OPTIMIZED hyperparameters:")
                    print(f"   numberOfTrees: {num_trees}")
                    print(f"   maxNodes: {max_nodes}")
                    print(f"   shrinkage: {shrinkage_param}")
                else:
                    num_trees = config.numberOfTrees
                    max_nodes = config.maxNodes
                    shrinkage_param = config.shrinkage
                    print(f"🎯 Training final classifier with DEFAULT hyperparameters:")
                    print(f"   numberOfTrees: {num_trees}")
                    print(f"   maxNodes: {max_nodes}")
                    print(f"   shrinkage: {shrinkage_param}")
                
                # Train classifier on training subset with final hyperparameters
                classifier_stable = cf.train_classifier(
                    train_points, train_stack, num_trees, max_nodes, shrinkage_param
                )
                
                # Evaluate on validation subset
                print("🔍 Evaluating final classifier performance on validation set...")
                validation_metrics = cf.evaluate_validation_performance(
                    classifier_stable, validation_points, train_stack, config.cdl_classes
                )
                
                # Print validation metrics
                cf.print_validation_metrics(validation_metrics)
                
                # Log validation metrics to journal
                cf.log_validation_metrics_to_journal(validation_metrics, training_year)
                
            else:
                # Original behavior - use all training points
                print("⚠️  Training without validation split (all points used for training)")
                
                # Random search requires validation split, so skip if validation is disabled
                if config.enable_random_search:
                    print("⚠️  Random search disabled: requires validation split (enable_validation=True)")
                
                classifier_stable = cf.train_classifier(
                    training_points, train_stack, config.numberOfTrees, config.maxNodes, config.shrinkage
                )

            # ------------------------ Predict for inference year ------------------------
            historical_mask = cf.get_historical_crop_mask(
                aoi, 
                inference_year - config.n_years_rotation_history, 
                inference_year, 
                config.cdl_classes
            )
            
            years_range_current = list(range(
                inference_year - config.n_years_rotation_history, 
                inference_year
            ))
            
            predict_stack = cf.add_rotation_features(years_range_current, historical_mask, config.cdl_classes, aoi_convexHull)

            # Add satellite features for prediction if requested
            if config.use_satellite_data == 1:
                date_start = f"{inference_year}-{config.month_start}-{config.day_start}"
                date_end = f"{inference_year}-{config.month_end}-{config.day_end}"
                
                s2 = cf.get_s2_sr_cld_col(aoi_convexHull, date_start, date_end, config.QA_BAND, config.CLEAR_THRESHOLD)
                filtered_collection = cf.process_satellite_data(s2, config.features_to_use, historical_mask)
                quality_mosaic_img = filtered_collection.qualityMosaic(config.quality_mosaic_band)
                predict_stack = predict_stack.addBands(quality_mosaic_img)

            predict_stack = predict_stack.rename(train_stack.bandNames())
            predicted_stable = predict_stack.classify(classifier_stable).rename("Predicted_Stable")

            # ------------------------ Naive prediction ------------------------
            naive_prediction = label_previous_year.rename("Naive_Copy")

            # ------------------------ Area Calculation ------------------------
            crop_areas_stable = cf.calculate_crop_areas(
                predicted_stable, "Predicted_Stable", config.cdl_classes, aoi, 
                config.m2_to_acres, config.resolution, config.county_scale_reduction_factor, config.tileScale
            )
            
            crop_areas_naive = cf.calculate_crop_areas(
                naive_prediction, "Naive_Copy", config.cdl_classes, aoi, 
                config.m2_to_acres, config.resolution, config.county_scale_reduction_factor, config.tileScale
            )

            # Store results for error analysis (using dynamic crop results)
            state_results[region_name] = crop_areas_stable
            
            # Create USDA data dictionary for flexible crops
            usda_data_dict = {
                'Corn': USDA_CORN_PLANTED_ACRES,
                'Soy': USDA_SOY_PLANTED_ACRES,
                'Wheat': USDA_WHEAT_PLANTED_ACRES,
                'Winter_Wheat': USDA_WINTER_WHEAT_PLANTED_ACRES,
                'Spring_Wheat': USDA_SPRING_WHEAT_PLANTED_ACRES,
                'Cotton': USDA_COTTON_PLANTED_ACRES,
                'Rice': USDA_RICE_PLANTED_ACRES,
                'Sorghum': USDA_SORGHUM_PLANTED_ACRES,
                'Hay': USDA_HAY_PLANTED_ACRES
            }
            
            # Clean per-state output for selected crops
            print(f"\n📍 {region_name}:")
            for crop in config.crops_to_process:
                predicted_area = crop_areas_stable.get(crop, 0)
                usda_area = None
                if crop in usda_data_dict and region_name in usda_data_dict[crop]:
                    usda_area = usda_data_dict[crop][region_name].get(inference_year, None)
                
                error_str = f"{((predicted_area - usda_area) / usda_area * 100):+5.1f}%" if usda_area else "No data"
                print(f"   {crop.upper():>6}: Pred={predicted_area:5.2f}M | USDA={usda_area or 'N/A':>5}M | Error={error_str}")
            
            # Update totals (maintaining backward compatibility for corn/soy)
            total_corn_area = total_corn_area + crop_areas_stable.get('Corn', 0)
            total_soy_area = total_soy_area + crop_areas_stable.get('Soy', 0)
            
            # Store classification data for later export
            if config.export_classification:
                classification_data[region_name] = {
                    'image': predicted_stable,
                    'geometry': aoi_convexHull,
                    'year': inference_year
                }
            
        except Exception as e:
            print(f'!!!!!!! skipping: {region_name} - Error: {e}')
            failed_states.append(region_name)

    # Show timing after all states processed
    processing_end = time.time()
    processing_duration = processing_end - processing_start
    processing_duration_str = str(timedelta(seconds=int(processing_duration)))
    
    print(f"\n⏱️  State Processing Completed in: {processing_duration_str} ({processing_duration:.1f} seconds)")
    print("="*60)

    Final_corn_area = total_corn_area / exterpolation_factor_corn
    Final_soy_area = total_soy_area / exterpolation_factor_soy

    print('total_FINAL corn_area all USA (million acres):', Final_corn_area)
    print('total_FINAL soy_area all USA (million acres):', Final_soy_area)

    return Final_corn_area, Final_soy_area, total_corn_area, total_soy_area, failed_states, state_results, classification_data, processing_duration_str


def main():
    """Main execution function"""
    start_time = time.time()
    start_datetime = get_local_time()
    
    print(f"🚀 Starting crop area classification at {start_datetime.strftime('%Y-%m-%d %H:%M:%S')} (Local Time)")
    
    # Initialize Earth Engine
    cf.initialize_earth_engine(
        config.SERVICE_ACCOUNT_FILE, 
        config.GEE_PROJECT, 
        config.FALLBACK_PROJECT
    )
    
    # Run the area calculation function
    print(f"Configuration: Training Year={config.training_year}, Inference Year={config.inference_year}")
    print(f"Satellite Data: {'Yes' if config.use_satellite_data else 'No'}")
    print(f"States: {'Corn/Soy Belt only' if config.only_corn_soy_belt_states else 'All states'}")
    print(f"Features: {config.features_to_use}")
    print(f"Date Range: {config.month_start}/{config.day_start} - {config.month_end}/{config.day_end}")
    print("="*50)
    
    Final_corn_area, Final_soy_area, total_corn_area, total_soy_area, failed_states, state_results, classification_data, processing_duration_str = Calculate_Corn_Soy_Area_USA()

    # Retry failed states if any
    if len(failed_states) > 0:
        print('Run again with the following failed states:', failed_states)
        
        Final_corn_area, Final_soy_area, total_corn_area2, total_soy_area2, failed_states2, state_results, retry_classification_data, retry_processing_duration_str = Calculate_Corn_Soy_Area_USA(
            total_corn_area, total_soy_area, state_results
        )
        # Merge classification data from retries
        classification_data.update(retry_classification_data)

    # Final results with timing
    end_time = time.time()
    end_datetime = get_local_time()
    duration = end_time - start_time
    duration_str = str(timedelta(seconds=int(duration)))
    
    
    # Calculate and display simplified errors vs USDA data
    if state_results:
        # Create USDA data dictionary for error calculation
        usda_data_dict = {
            'Corn': USDA_CORN_PLANTED_ACRES,
            'Soy': USDA_SOY_PLANTED_ACRES,
            'Wheat': USDA_WHEAT_PLANTED_ACRES,
            'Winter_Wheat': USDA_WINTER_WHEAT_PLANTED_ACRES,
            'Spring_Wheat': USDA_SPRING_WHEAT_PLANTED_ACRES,
            'Cotton': USDA_COTTON_PLANTED_ACRES,
            'Rice': USDA_RICE_PLANTED_ACRES,
            'Sorghum': USDA_SORGHUM_PLANTED_ACRES,
            'Hay': USDA_HAY_PLANTED_ACRES
        }
        
        error_results = cf.calculate_errors_vs_usda(
            state_results, 
            usda_data_dict,
            config.inference_year,
            config.crops_to_process
        )
        
        # Print detailed per-state results table
        print_detailed_results_table(
            state_results, 
            error_results, 
            processing_duration_str, 
            Final_corn_area, 
            Final_soy_area, 
            config.inference_year, 
            usda_data_dict
        )
        
        print_simplified_error_summary(error_results, config.inference_year)
    
    print(f"\n⏱️  TIMING INFORMATION:")
    print(f"Start Time: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')} (Local Time)")
    print(f"End Time: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')} (Local Time)")
    print(f"Total Duration: {duration_str} ({duration:.1f} seconds)")
    
    print(f"\n📋 COMPLETE CONFIGURATION DUMP:")
    print('='*60)
    
    # Main Input Parameters
    print("🗓️  YEARS:")
    print(f"   training_year = {config.training_year}")
    print(f"   inference_year = {config.inference_year}")
    print(f"   selected_year = {config.selected_year}")
    
    # Date Range
    print("\n📅 DATE RANGE:")
    print(f"   day_start = '{config.day_start}'")
    print(f"   month_start = '{config.month_start}'")
    print(f"   day_end = '{config.day_end}'")
    print(f"   month_end = '{config.month_end}'")
    
    # Model Configuration
    print("\n⚙️  MODEL CONFIGURATION:")
    print(f"   use_satellite_data = {config.use_satellite_data}")
    print(f"   only_corn_soy_belt_states = {config.only_corn_soy_belt_states}")
    print(f"   corn_or_soy_states = {config.corn_or_soy_states}")
    
    # Spatial Resolution
    print("\n🌍 SPATIAL RESOLUTION:")
    print(f"   resolution = {config.resolution}")
    print(f"   county_scale_reduction_factor = {config.county_scale_reduction_factor}")
    
    # Crop Selection
    print("\n🌾 CROP SELECTION:")
    print(f"   crops_to_process = {config.crops_to_process}")
    print(f"   cdl_classes = {config.cdl_classes}")
    
    # Processing Parameters
    print("\n⚡ PROCESSING PARAMETERS:")
    print(f"   m2_to_acres = {config.m2_to_acres}")
    print(f"   QA_BAND = '{config.QA_BAND}'")
    print(f"   CLEAR_THRESHOLD = {config.CLEAR_THRESHOLD}")
    print(f"   tileScale = {config.tileScale}")
    
    # Crop Rotation
    print("\n🔄 CROP ROTATION:")
    print(f"   n_years_rotation_history = {config.n_years_rotation_history}")
    
    # Sampling Parameters
    print("\n📊 SAMPLING:")
    print(f"   n_points_per_class_satellite = {config.n_points_per_class_satellite}")
    print(f"   n_points_per_class_no_satellite = {config.n_points_per_class_no_satellite}")
    
    # XGBoost Parameters
    print("\n🌳 XGBOOST PARAMETERS:")
    print(f"   numberOfTrees = {config.numberOfTrees}")
    print(f"   maxNodes = {config.maxNodes}")
    print(f"   shrinkage = {config.shrinkage}")
    
    # Validation Parameters
    print("\n✅ VALIDATION:")
    print(f"   enable_validation = {config.enable_validation}")
    print(f"   train_validation_split = {config.train_validation_split}")
    print(f"   validation_seed = {config.validation_seed}")
    
    # CDL Confidence Parameters
    print("\n🎯 CDL CONFIDENCE FILTERING:")
    print(f"   enable_cdl_confidence_filtering = {config.enable_cdl_confidence_filtering}")
    print(f"   cdl_confidence_threshold = {config.cdl_confidence_threshold}")
    
    if config.enable_cdl_confidence_filtering:
        print(f"   → Only pixels with CDL confidence ≥ {config.cdl_confidence_threshold}% will be used for training")
    else:
        print(f"   → All CDL pixels will be used for training (no confidence filtering)")
    
    # Random Search Parameters
    print("\n🔍 RANDOM SEARCH HYPERPARAMETER OPTIMIZATION:")
    print(f"   enable_random_search = {config.enable_random_search}")
    print(f"   random_search_iterations = {config.random_search_iterations}")
    print(f"   random_search_seed = {config.random_search_seed}")
    print(f"   random_search_scoring_metric = '{config.random_search_scoring_metric}'")
    print(f"   save_random_search_results = {config.save_random_search_results}")
    print(f"   random_search_results_dir = '{config.random_search_results_dir}'")
    
    if config.enable_random_search:
        print(f"   → Random search will optimize hyperparameters using {config.random_search_iterations} iterations")
        print(f"   → Search ranges: {config.hyperparameter_search_ranges}")
    else:
        print(f"   → Random search disabled, using default hyperparameters")
    
    # Feature Selection
    print("\n🛰️  FEATURES:")
    print(f"   features_to_use = {config.features_to_use}")
    print(f"   quality_mosaic_band = '{config.quality_mosaic_band}'")
    
    # Extrapolation Ratios
    print("\n📈 EXTRAPOLATION:")
    print(f"   corn_extepolation_ratio = {config.corn_extepolation_ratio}")
    print(f"   soy_extepolation_ratio = {config.soy_extepolation_ratio}")
    
    # States
    calc_params = config.get_calculated_parameters()
    print("\n🗺️  STATES:")
    print(f"   corn_soy_belt_states = {config.corn_soy_belt_states}")
    print(f"   states_to_use = {calc_params['states_to_use']}")
    print(f"   exterpolation_factor_corn = {calc_params['exterpolation_factor_corn']}")
    print(f"   exterpolation_factor_soy = {calc_params['exterpolation_factor_soy']}")
    
    # Authentication
    print("\n🔐 AUTHENTICATION:")
    print(f"   SERVICE_ACCOUNT_FILE = '{config.SERVICE_ACCOUNT_FILE}'")
    print(f"   GEE_PROJECT = '{config.GEE_PROJECT}'")
    print(f"   FALLBACK_PROJECT = '{config.FALLBACK_PROJECT}'")
    
    # Export Configuration
    print("\n📤 EXPORT:")
    print(f"   export_classification = {config.export_classification}")
    print(f"   export_asset_project = '{config.export_asset_project}'")
    print(f"   export_asset_folder = '{config.export_asset_folder}'")
    print(f"   export_resolution = {config.export_resolution}")
    
    # Calculated Parameters
    print("\n🧮 CALCULATED:")
    print(f"   pixel_area_m2 = {calc_params['pixel_area_m2']}")
    
    print('='*60)
    
    # Export all classification assets at the very end
    if config.export_classification and classification_data:
        print(f"\n🚀 EXPORTING CLASSIFICATION ASSETS:")
        print("="*60)
        for state_name, data in classification_data.items():
            print(f"\n📊 Exporting {state_name}...")
            asset_id = cf.export_classification_to_asset(
                data['image'], 
                data['geometry'], 
                state_name, 
                data['year'],
                config.export_asset_project,
                config.export_asset_folder
            )
            if asset_id:
                print(f"✅ {state_name} exported successfully")
            else:
                print(f"❌ {state_name} export failed")
        print("="*60)


if __name__ == "__main__":
    main()