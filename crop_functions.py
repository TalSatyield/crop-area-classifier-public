# -*- coding: utf-8 -*-
"""
Core functions for Crop Classifier
Contains all the data processing, feature engineering, and classification functions
"""

import ee
from google.oauth2 import service_account


def initialize_earth_engine(service_account_file, gee_project, fallback_project):
    """Initialize Google Earth Engine with service account authentication"""
    print(f"Earth Engine version: {ee.__version__}")
    
    try:
        # Use service account authentication with proper scopes
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=['https://www.googleapis.com/auth/earthengine']
        )
        ee.Initialize(credentials=credentials, project=gee_project)
        print('Service account authentication successful')
    except Exception as e:
        print(f'Service account failed: {e}')
        # Fallback to original authentication method
        try:
            ee.Initialize(project=fallback_project)
            print('Fallback authentication successful')
        except Exception as e:
            ee.Authenticate()
            ee.Initialize(project=fallback_project)
            print('Interactive authentication completed')


def load_cdl(year, historical_mask, aoi_convexHull):
    """Load CDL data for a specific year"""
    return ee.ImageCollection("USDA/NASS/CDL") \
        .filter(ee.Filter.calendarRange(year, year, "year")) \
        .first() \
        .select("cropland") \
        .clip(aoi_convexHull) \
        .updateMask(historical_mask) \
        .rename(f"CDL_{year}")


def encode_label(image, cdl_classes):
    """Encode crop labels from CDL classes"""
    # Fast path for 2 crops (original implementation)
    if len(cdl_classes) == 3 and "Corn" in cdl_classes and "Soy" in cdl_classes:
        return (
            image.where(image.eq(cdl_classes["Corn"]), cdl_classes["Corn"])
                .where(image.eq(cdl_classes["Soy"]), cdl_classes["Soy"])
                .where(image.neq(cdl_classes["Corn"]).And(image.neq(cdl_classes["Soy"])), 0)
                .rename("crop_label")
        )
    
    # Multi-crop path (for 3+ crops)
    result = image
    
    # Apply encoding for each crop
    if "Corn" in cdl_classes:
        result = result.where(image.eq(cdl_classes["Corn"]), cdl_classes["Corn"])
    if "Soy" in cdl_classes:
        result = result.where(image.eq(cdl_classes["Soy"]), cdl_classes["Soy"])
    if "Sorghum" in cdl_classes:
        result = result.where(image.eq(cdl_classes["Sorghum"]), cdl_classes["Sorghum"])
    
    # Create mask for all crops
    crop_mask = ee.Image.constant(0)
    for crop_name, crop_code in cdl_classes.items():
        if crop_name != "Other":
            crop_mask = crop_mask.Or(image.eq(crop_code))
    
    # Set non-crop pixels to 0 (Other)
    result = result.where(crop_mask, result).where(crop_mask.Not(), 0)
    
    return result.rename("crop_label")


def add_rotation_features(history_years, historical_mask, cdl_classes, aoi_convexHull):
    """Add crop rotation features from historical years"""
    # Fast path for 2 crops (original implementation)
    if len(cdl_classes) == 3 and "Corn" in cdl_classes and "Soy" in cdl_classes:
        features = []
        for y in history_years:
            cdl = load_cdl(y, historical_mask, aoi_convexHull)
            was_corn = cdl.eq(cdl_classes["Corn"]).rename(f"was_corn_{y}")
            was_soy = cdl.eq(cdl_classes["Soy"]).rename(f"was_soy_{y}")
            features.extend([was_corn, was_soy])
        return ee.Image.cat(features)
    
    # Multi-crop path (for 3+ crops)
    features = []
    for y in history_years:
        cdl = load_cdl(y, historical_mask, aoi_convexHull)
        
        # Add features for each crop (same pattern as original)
        if "Corn" in cdl_classes:
            was_corn = cdl.eq(cdl_classes["Corn"]).rename(f"was_corn_{y}")
            features.append(was_corn)
        if "Soy" in cdl_classes:
            was_soy = cdl.eq(cdl_classes["Soy"]).rename(f"was_soy_{y}")
            features.append(was_soy)
        if "Sorghum" in cdl_classes:
            was_sorghum = cdl.eq(cdl_classes["Sorghum"]).rename(f"was_sorghum_{y}")
            features.append(was_sorghum)
            
    return ee.Image.cat(features)


def get_historical_crop_mask(aoi, start_year, end_year, cdl_classes):
    """
    Get historical crop mask from CDL collection.
    
    Args:
        aoi: Area of Interest geometry
        start_year: Start year (e.g., 2019)
        end_year: End year (e.g., 2023)
        cdl_classes: Dictionary with crop codes
    
    Returns:
        ee.Image: Mask of pixels that were crops in any year
    """
    # Fast path for 2 crops (original implementation)
    if len(cdl_classes) == 3 and "Corn" in cdl_classes and "Soy" in cdl_classes:
        crop_codes = [cdl_classes["Corn"], cdl_classes["Soy"]]
    else:
        # Multi-crop path
        crop_codes = []
        for crop_name, crop_code in cdl_classes.items():
            if crop_name != "Other":
                crop_codes.append(crop_code)
    aoi_convexHull = aoi.convexHull()
    aoi_fc = ee.FeatureCollection(aoi)
    
    # Get CDL collection for date range
    cdl_collection = ee.ImageCollection("USDA/NASS/CDL") \
        .filterBounds(aoi_convexHull) \
        .filterDate(f'{start_year}-01-01', f'{end_year}-12-31') \
        .select('cropland')

    # Function to create mask for crop codes
    def create_crop_mask(image):
        mask = ee.Image.constant(0)
        for code in crop_codes:
            mask = mask.Or(image.eq(code))
        return mask

    # Apply to collection and reduce (any non-zero pixel across years)
    crop_masks = cdl_collection.map(create_crop_mask)
    historical_mask = crop_masks.reduce(ee.Reducer.anyNonZero())

    return historical_mask.clipToCollection(aoi_fc)


def get_s2_sr_cld_col(aoi_convexHull, start_date, end_date, qa_band, clear_threshold):
    """Load and filter Sentinel-2 data with cloud masking"""
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
        .filterBounds(aoi_convexHull) \
        .filterDate(start_date, end_date)

    csPlus = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED') \
        .filterBounds(aoi_convexHull) \
        .filterDate(start_date, end_date)

    s2_filtered = s2.linkCollection(csPlus, [qa_band]).map(
        lambda img: img.updateMask(img.select(qa_band).gte(clear_threshold))
    )
    return s2_filtered


def select_bands(band_list, historical_mask):
    """Create function to select bands and apply mask"""
    def _select(img):
        return img.select(band_list).updateMask(historical_mask)
    return _select


def add_DOY_band(image):
    """Add Day of Year band to image"""
    date = ee.Date(image.get('system:time_start'))
    doy = date.getRelative('day', 'year').int()
    doy_band = ee.Image.constant(doy).rename('DOY').toInt()
    return image.addBands(doy_band)


def addGCVI(img):
    """Add Green Chlorophyll Vegetation Index"""
    gcvi = img.expression(
        "(NIR / GREEN) - 1", {
            "NIR": img.select("B8"),
            "GREEN": img.select("B3")
        }).rename("GCVI")
    return img.addBands(gcvi)


def add_NDRE2(img):
    """Add Normalized Difference Red Edge Index 2"""
    ndre = img.expression(
        "(NIR - RE) / (NIR + RE)", {
            'NIR': img.select('B8'),
            'RE': img.select('B6')
        }).rename('NDRE')
    return img.addBands(ndre)


def calculate_crop_areas(image, band_name, cdl_classes, aoi, m2_to_acres, resolution, county_scale_reduction_factor, tileScale):
    """Calculate areas for all crops from classified image"""
    aoi_convexHull = aoi.convexHull()
    aoi_fc = ee.FeatureCollection(aoi)
    
    crop_areas = {}
    
    # Calculate area for each crop (excluding "Other")
    for crop_name, crop_code in cdl_classes.items():
        if crop_name != "Other":  # Skip "Other" as it's background
            crop_mask = image.eq(crop_code)
            areaImage_clipped = crop_mask.clipToCollection(aoi_fc)
            
            stats = areaImage_clipped.reduceRegion(**{
                'reducer': ee.Reducer.sum(),
                'geometry': aoi_convexHull,
                'scale': resolution * county_scale_reduction_factor,
                'maxPixels': 1e13,
                'tileScale': tileScale
            })
            
            area_info = stats.getInfo()
            area_m2 = area_info[band_name]
            area_m2 = (area_m2 * (resolution * county_scale_reduction_factor) ** 2)
            crop_area = area_m2 * m2_to_acres
            
            # Convert to millions of acres and round
            crop_areas[crop_name] = round(crop_area / 10**6, 3)
    
    return crop_areas


def calculate_corn_soy_areas(image, band_name, cdl_classes, aoi, m2_to_acres, resolution, county_scale_reduction_factor, tileScale):
    """Backward compatibility wrapper for calculate_crop_areas"""
    crop_areas = calculate_crop_areas(image, band_name, cdl_classes, aoi, m2_to_acres, resolution, county_scale_reduction_factor, tileScale)
    
    # Return in the original format for backward compatibility
    soy_area = crop_areas.get("Soy", 0)
    corn_area = crop_areas.get("Corn", 0)
    
    return soy_area, corn_area


def process_satellite_data(s2, features_to_use, historical_mask):
    """Process satellite data and add requested features"""
    if 'DOY' in features_to_use:
        s2 = s2.map(add_DOY_band)
    if 'GCVI' in features_to_use:
        s2 = s2.map(addGCVI)
    if 'NDRE2' in features_to_use:
        s2 = s2.map(add_NDRE2)
    
    filtered_collection = s2.map(select_bands(features_to_use, historical_mask))
    return filtered_collection


def create_training_points(training_image, aoi_fc, aoi_convexHull, cdl_classes, classPoints, resolution, county_scale_reduction_factor):
    """Create stratified training points from training image"""
    # Fast path for 2 crops (original implementation)
    if len(cdl_classes) == 3 and "Corn" in cdl_classes and "Soy" in cdl_classes:
        training_points = training_image.clipToCollection(aoi_fc).stratifiedSample(
            numPoints=0,
            classBand="crop_label",
            classValues=[0, cdl_classes["Corn"], cdl_classes["Soy"]],
            classPoints=classPoints,
            region=aoi_convexHull,
            scale=resolution * county_scale_reduction_factor,
            seed=42,
            geometries=False
        )
        return training_points
    
    # Multi-crop path
    # Build class values list: [0, crop1_code, crop2_code, ...]
    class_values = [0]  # Start with "Other" (0)
    for crop_name, crop_code in cdl_classes.items():
        if crop_name != "Other":
            class_values.append(crop_code)
    
    # Sort to ensure consistent order
    class_values.sort()
    
    training_points = training_image.clipToCollection(aoi_fc).stratifiedSample(
        numPoints=0,
        classBand="crop_label",
        classValues=class_values,
        classPoints=classPoints,
        region=aoi_convexHull,
        scale=resolution * county_scale_reduction_factor,
        seed=42,
        geometries=False
    )
    return training_points


def train_classifier(training_points, train_stack, numberOfTrees, maxNodes, shrinkage):
    """Train XGBoost classifier"""
    classifier_stable = ee.Classifier.smileGradientTreeBoost(
        numberOfTrees=numberOfTrees,
        maxNodes=maxNodes,
        shrinkage=shrinkage
    ).train(
        features=training_points,
        classProperty="crop_label",
        inputProperties=train_stack.bandNames()
    )
    return classifier_stable


def calculate_errors_vs_usda(results_dict, usda_corn_data, usda_soy_data, year):
    """
    Calculate errors between model predictions and USDA reference data
    
    Args:
        results_dict: Dictionary with state names as keys and prediction results as values
        usda_corn_data: Dictionary with USDA corn data by state and year
        usda_soy_data: Dictionary with USDA soy data by state and year  
        year: Year for which to get USDA data
        
    Returns:
        Dictionary with error statistics per state and overall
    """
    error_results = {
        'per_state': {},
        'overall': {
            'corn': {'total_predicted': 0, 'total_usda': 0, 'states_with_data': 0, 'states_missing_data': []},
            'soy': {'total_predicted': 0, 'total_usda': 0, 'states_with_data': 0, 'states_missing_data': []}
        }
    }
    
    for state_name, predictions in results_dict.items():
        state_errors = {'corn': {}, 'soy': {}}
        
        # Get predictions (convert to match USDA units - already in million acres)
        corn_pred = predictions.get('Corn', 0)
        soy_pred = predictions.get('Soy', 0)
        
        # Get USDA reference data
        corn_usda = None
        soy_usda = None
        
        if state_name in usda_corn_data and year in usda_corn_data[state_name]:
            corn_usda = usda_corn_data[state_name][year]
            
        if state_name in usda_soy_data and year in usda_soy_data[state_name]:
            soy_usda = usda_soy_data[state_name][year]
        
        # Calculate corn errors
        if corn_usda is not None:
            corn_error = corn_pred - corn_usda
            corn_error_pct = (corn_error / corn_usda * 100) if corn_usda != 0 else 0
            corn_abs_error_pct = abs(corn_error_pct)
            
            state_errors['corn'] = {
                'predicted': corn_pred,
                'usda': corn_usda,
                'error': corn_error,
                'error_pct': corn_error_pct,
                'abs_error_pct': corn_abs_error_pct
            }
            
            # Add to overall totals
            error_results['overall']['corn']['total_predicted'] += corn_pred
            error_results['overall']['corn']['total_usda'] += corn_usda
            error_results['overall']['corn']['states_with_data'] += 1
        else:
            state_errors['corn'] = {'error': 'No USDA data available'}
            error_results['overall']['corn']['states_missing_data'].append(state_name)
        
        # Calculate soy errors  
        if soy_usda is not None:
            soy_error = soy_pred - soy_usda
            soy_error_pct = (soy_error / soy_usda * 100) if soy_usda != 0 else 0
            soy_abs_error_pct = abs(soy_error_pct)
            
            state_errors['soy'] = {
                'predicted': soy_pred,
                'usda': soy_usda,
                'error': soy_error,
                'error_pct': soy_error_pct,
                'abs_error_pct': soy_abs_error_pct
            }
            
            # Add to overall totals
            error_results['overall']['soy']['total_predicted'] += soy_pred
            error_results['overall']['soy']['total_usda'] += soy_usda
            error_results['overall']['soy']['states_with_data'] += 1
        else:
            state_errors['soy'] = {'error': 'No USDA data available'}
            error_results['overall']['soy']['states_missing_data'].append(state_name)
            
        error_results['per_state'][state_name] = state_errors
    
    # Calculate overall error statistics
    for crop in ['corn', 'soy']:
        overall = error_results['overall'][crop]
        if overall['total_usda'] > 0:
            overall['total_error'] = overall['total_predicted'] - overall['total_usda']
            overall['total_error_pct'] = (overall['total_error'] / overall['total_usda']) * 100
            overall['total_abs_error_pct'] = abs(overall['total_error_pct'])
        
    return error_results


def calculate_errors_vs_usda_multi_crop(results_dict, usda_data_dict, year):
    """
    Calculate errors between model predictions and USDA reference data for multiple crops
    
    Args:
        results_dict: Dictionary with state names as keys and prediction results as values
        usda_data_dict: Dictionary with crop names as keys and USDA data dictionaries as values
        year: Year for which to get USDA data
        
    Returns:
        Dictionary with error statistics per state and overall for all crops
    """
    error_results = {
        'per_state': {},
        'overall': {}
    }
    
    # Initialize overall results for each crop
    for crop_name in usda_data_dict.keys():
        error_results['overall'][crop_name.lower()] = {
            'total_predicted': 0, 
            'total_usda': 0, 
            'states_with_data': 0, 
            'states_missing_data': []
        }
    
    for state_name, predictions in results_dict.items():
        state_errors = {}
        
        for crop_name, usda_crop_data in usda_data_dict.items():
            crop_key = crop_name.lower()
            state_errors[crop_key] = {}
            
            # Get prediction (convert to match USDA units - already in million acres)
            crop_pred = predictions.get(crop_name, 0)
            
            # Get USDA reference data
            crop_usda = None
            if state_name in usda_crop_data and year in usda_crop_data[state_name]:
                crop_usda = usda_crop_data[state_name][year]
            
            # Calculate errors
            if crop_usda is not None:
                crop_error = crop_pred - crop_usda
                crop_error_pct = (crop_error / crop_usda * 100) if crop_usda != 0 else 0
                crop_abs_error_pct = abs(crop_error_pct)
                
                state_errors[crop_key] = {
                    'predicted': crop_pred,
                    'usda': crop_usda,
                    'error': crop_error,
                    'error_pct': crop_error_pct,
                    'abs_error_pct': crop_abs_error_pct
                }
                
                # Add to overall totals
                error_results['overall'][crop_key]['total_predicted'] += crop_pred
                error_results['overall'][crop_key]['total_usda'] += crop_usda
                error_results['overall'][crop_key]['states_with_data'] += 1
            else:
                state_errors[crop_key] = {'error': 'No USDA data available'}
                error_results['overall'][crop_key]['states_missing_data'].append(state_name)
                
        error_results['per_state'][state_name] = state_errors
    
    # Calculate overall error statistics
    for crop_key in error_results['overall'].keys():
        overall = error_results['overall'][crop_key]
        if overall['total_usda'] > 0:
            overall['total_error'] = overall['total_predicted'] - overall['total_usda']
            overall['total_error_pct'] = (overall['total_error'] / overall['total_usda']) * 100
            overall['total_abs_error_pct'] = abs(overall['total_error_pct'])
        
    return error_results


def print_error_report(error_results, year):
    """Print formatted error report"""
    print(f"\n{'='*80}")
    print(f"ERROR ANALYSIS vs USDA DATA for {year}")
    print('='*80)
    
    # Per state errors
    print("\nPER STATE ERRORS:")
    print("-" * 80)
    print(f"{'State':<15} {'Crop':<6} {'Predicted':<10} {'USDA':<10} {'Error':<8} {'Error %':<10}")
    print("-" * 80)
    
    for state_name, errors in error_results['per_state'].items():
        for crop in ['corn', 'soy']:
            crop_errors = errors[crop]
            if isinstance(crop_errors, dict) and 'error' in crop_errors:
                if crop_errors['error'] == 'No USDA data available':
                    print(f"{state_name:<15} {crop.upper():<6} {'N/A':<10} {'N/A':<10} {'No data':<8} {'N/A':<10}")
                else:
                    print(f"{state_name:<15} {crop.upper():<6} {crop_errors['predicted']:<10.3f} {crop_errors['usda']:<10.3f} {crop_errors['error']:<8.3f} {crop_errors['error_pct']:<10.1f}%")
    
    # Overall statistics
    print(f"\n{'='*80}")
    print("OVERALL STATISTICS:")
    print('='*80)
    
    for crop in ['corn', 'soy']:
        overall = error_results['overall'][crop]
        print(f"\n{crop.upper()}:")
        print(f"  States with USDA data: {overall['states_with_data']}")
        if overall['states_missing_data']:
            print(f"  States missing USDA data: {', '.join(overall['states_missing_data'])}")
        
        if 'total_error_pct' in overall:
            print(f"  Total Predicted: {overall['total_predicted']:.3f} million acres")
            print(f"  Total USDA: {overall['total_usda']:.3f} million acres")
            print(f"  Total Error: {overall['total_error']:.3f} million acres")
            print(f"  Total Error %: {overall['total_error_pct']:.1f}%")
    
    print('='*80)