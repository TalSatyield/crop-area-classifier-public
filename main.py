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
from usda_data import USDA_CORN_PLANTED_ACRES, USDA_SOY_PLANTED_ACRES


def get_local_time():
    """Get current time in local timezone (assuming UTC+3 based on user input)"""
    utc_time = datetime.now(timezone.utc)
    local_time = utc_time + timedelta(hours=3)  # UTC+3 timezone
    return local_time


def print_simplified_error_summary(error_results, year):
    """Print simplified error summary showing only key metrics"""
    print(f"\n📊 VALIDATION vs USDA DATA ({year}):")
    print("-" * 50)
    
    # Overall statistics for all crops that have data
    for crop_key, overall in error_results['overall'].items():
        crop_name = crop_key.upper()
        
        if 'total_error_pct' in overall:
            predicted = overall['total_predicted']
            usda = overall['total_usda']
            error_pct = overall['total_error_pct']
            
            print(f"{crop_name:7}: Predicted={predicted:6.1f}M acres | USDA={usda:6.1f}M acres | Error={error_pct:+5.1f}%")
        else:
            print(f"{crop_name:7}: No USDA data available")
    
    print("-" * 50)


def Calculate_Corn_Soy_Area_USA(total_crop_areas=None, state_results=None):
    """
    Main function to calculate crop areas for USA states
    
    Args:
        total_crop_areas: Dictionary with running totals of crop areas (for retry runs)
        state_results: Dictionary to store per-state results for error analysis
    
    Returns:
        tuple: (Final_crop_areas, total_crop_areas, failed_states, state_results)
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
    
    # Initialize dictionaries if not provided
    if state_results is None:
        state_results = {}
        
    if total_crop_areas is None:
        total_crop_areas = {crop: 0 for crop in config.crops_to_analyze}

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

            # Create training points
            # Fast path for 2 crops (original implementation)
            if len(config.cdl_classes) == 3 and "Corn" in config.cdl_classes and "Soy" in config.cdl_classes:
                if config.use_satellite_data == 1:
                    classPoints = [config.n_points_per_class_satellite] * 3
                else:
                    classPoints = [config.n_points_per_class_no_satellite] * 3
            else:
                # Multi-crop path
                classPoints = config.get_class_points()
                
            training_points = cf.create_training_points(
                training_image, aoi_fc, aoi_convexHull, config.cdl_classes, 
                classPoints, config.resolution, config.county_scale_reduction_factor
            )

            # ------------------------ Train Classifier ------------------------
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
            # Fast path for 2 crops (original implementation)
            if len(config.cdl_classes) == 3 and "Corn" in config.cdl_classes and "Soy" in config.cdl_classes:
                soy_stable, corn_stable = cf.calculate_corn_soy_areas(
                    predicted_stable, "Predicted_Stable", config.cdl_classes, aoi, 
                    config.m2_to_acres, config.resolution, config.county_scale_reduction_factor, config.tileScale
                )
                
                soy_naive, corn_naive = cf.calculate_corn_soy_areas(
                    naive_prediction, "Naive_Copy", config.cdl_classes, aoi, 
                    config.m2_to_acres, config.resolution, config.county_scale_reduction_factor, config.tileScale
                )
                
                # Create crop_areas_stable for compatibility
                crop_areas_stable = {"Corn": corn_stable, "Soy": soy_stable}
                
            else:
                # Multi-crop path
                crop_areas_stable = cf.calculate_crop_areas(
                    predicted_stable, "Predicted_Stable", config.cdl_classes, aoi, 
                    config.m2_to_acres, config.resolution, config.county_scale_reduction_factor, config.tileScale
                )
                
                crop_areas_naive = cf.calculate_crop_areas(
                    naive_prediction, "Naive_Copy", config.cdl_classes, aoi, 
                    config.m2_to_acres, config.resolution, config.county_scale_reduction_factor, config.tileScale
                )
                
                # Extract individual crop areas for backward compatibility
                soy_stable = crop_areas_stable.get("Soy", 0)
                corn_stable = crop_areas_stable.get("Corn", 0)
                sorghum_stable = crop_areas_stable.get("Sorghum", 0)
                
                soy_naive = crop_areas_naive.get("Soy", 0)
                corn_naive = crop_areas_naive.get("Corn", 0)
                sorghum_naive = crop_areas_naive.get("Sorghum", 0)

            # Store results for error analysis
            state_results[region_name] = crop_areas_stable.copy()
            
            # Fast path for 2 crops (original reporting)
            if len(config.cdl_classes) == 3 and "Corn" in config.cdl_classes and "Soy" in config.cdl_classes:
                # Get USDA data for comparison
                corn_usda = USDA_CORN_PLANTED_ACRES.get(region_name, {}).get(inference_year, None)
                soy_usda = USDA_SOY_PLANTED_ACRES.get(region_name, {}).get(inference_year, None)
                
                # Calculate errors
                corn_error = f"{((corn_stable - corn_usda) / corn_usda * 100):+5.1f}%" if corn_usda else "No data"
                soy_error = f"{((soy_stable - soy_usda) / soy_usda * 100):+5.1f}%" if soy_usda else "No data"
                
                # Clean per-state output
                print(f"\n📍 {region_name}:")
                print(f"   CORN: Pred={corn_stable:5.2f}M | USDA={corn_usda or 'N/A':>5}M | Error={corn_error}")
                print(f"   SOY:  Pred={soy_stable:5.2f}M | USDA={soy_usda or 'N/A':>5}M | Error={soy_error}")
                
            else:
                # Multi-crop reporting
                print(f"\n📍 {region_name}:")
                
                # Display results for each crop
                for crop_name in config.crops_to_analyze:
                    pred_area = crop_areas_stable.get(crop_name, 0)
                    
                    # Get USDA data if available
                    usda_area = None
                    if crop_name == "Corn":
                        usda_area = USDA_CORN_PLANTED_ACRES.get(region_name, {}).get(inference_year, None)
                    elif crop_name == "Soy":
                        usda_area = USDA_SOY_PLANTED_ACRES.get(region_name, {}).get(inference_year, None)
                    elif crop_name == "Sorghum":
                        from usda_data import USDA_SORGHUM_PLANTED_ACRES
                        usda_area = USDA_SORGHUM_PLANTED_ACRES.get(region_name, {}).get(inference_year, None)
                    # Add more USDA data sources here when available for other crops
                    
                    # Calculate error
                    if usda_area:
                        error = f"{((pred_area - usda_area) / usda_area * 100):+5.1f}%"
                        usda_display = f"{usda_area:5.2f}M"
                    else:
                        error = "No data"
                        usda_display = "N/A"
                    
                    print(f"   {crop_name.upper():<7}: Pred={pred_area:5.2f}M | USDA={usda_display:>7} | Error={error}")
            
            # Fast path for 2 crops (original accumulation)
            if len(config.cdl_classes) == 3 and "Corn" in config.cdl_classes and "Soy" in config.cdl_classes:
                total_crop_areas["Corn"] += corn_stable
                total_crop_areas["Soy"] += soy_stable
            else:
                # Multi-crop accumulation
                for crop_name in config.crops_to_analyze:
                    total_crop_areas[crop_name] += crop_areas_stable.get(crop_name, 0)
            
        except Exception as e:
            print(f'!!!!!!! skipping: {region_name} - Error: {e}')
            failed_states.append(region_name)

    # Show timing after all states processed
    processing_end = time.time()
    processing_duration = processing_end - processing_start
    processing_duration_str = str(timedelta(seconds=int(processing_duration)))
    
    print(f"\n⏱️  State Processing Completed in: {processing_duration_str} ({processing_duration:.1f} seconds)")
    print("="*60)

    # Calculate final areas with extrapolation factors
    Final_crop_areas = {}
    for crop_name in config.crops_to_analyze:
        if crop_name == "Corn":
            Final_crop_areas[crop_name] = total_crop_areas[crop_name] / exterpolation_factor_corn
        elif crop_name == "Soy":
            Final_crop_areas[crop_name] = total_crop_areas[crop_name] / exterpolation_factor_soy
        else:
            # For other crops, use corn extrapolation factor as default (can be made configurable)
            Final_crop_areas[crop_name] = total_crop_areas[crop_name] / exterpolation_factor_corn

    # Print final areas for all crops
    for crop_name in config.crops_to_analyze:
        print(f'total_FINAL {crop_name.lower()}_area all USA (million acres): {Final_crop_areas[crop_name]}')

    return Final_crop_areas, total_crop_areas, failed_states, state_results


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
    
    Final_crop_areas, total_crop_areas, failed_states, state_results = Calculate_Corn_Soy_Area_USA()

    # Retry failed states if any
    if len(failed_states) > 0:
        print('Run again with the following failed states:', failed_states)
        
        Final_crop_areas, total_crop_areas, failed_states2, state_results = Calculate_Corn_Soy_Area_USA(
            total_crop_areas, state_results
        )

    # Final results with timing
    end_time = time.time()
    end_datetime = get_local_time()
    duration = end_time - start_time
    duration_str = str(timedelta(seconds=int(duration)))
    
    print('\n' + '='*60)
    print('🎯 FINAL RESULTS:')
    for crop_name in config.crops_to_analyze:
        print(f'{crop_name} Area (million acres): {Final_crop_areas[crop_name]}')
    print('='*60)
    
    # Calculate and display simplified errors vs USDA data
    if state_results:
        # Create USDA data dictionary for available crops
        from usda_data import USDA_SORGHUM_PLANTED_ACRES
        usda_data_dict = {
            'Corn': USDA_CORN_PLANTED_ACRES,
            'Soy': USDA_SOY_PLANTED_ACRES,
            'Sorghum': USDA_SORGHUM_PLANTED_ACRES
        }
        
        error_results = cf.calculate_errors_vs_usda_multi_crop(
            state_results, 
            usda_data_dict,
            config.inference_year
        )
        print_simplified_error_summary(error_results, config.inference_year)
    
    print(f"\n⏱️  TIMING INFORMATION:")
    print(f"Start Time: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')} (Local Time)")
    print(f"End Time: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')} (Local Time)")
    print(f"Total Duration: {duration_str} ({duration:.1f} seconds)")
    print('='*60)


if __name__ == "__main__":
    main()