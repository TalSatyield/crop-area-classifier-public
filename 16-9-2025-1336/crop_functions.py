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
        # Try the exact same method as working 28-8 reference first
        print("   📡 Initializing Earth Engine...")
        ee.Authenticate()
        ee.Initialize(project='satyield-algo')
        print('Authentication successful with satyield-algo project')
    except Exception as e:
        print(f'Direct satyield-algo authentication failed: {e}')
        try:
            # Fallback to service account authentication 
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file,
                scopes=['https://www.googleapis.com/auth/earthengine']
            )
            ee.Initialize(credentials=credentials, project=gee_project)
            print('Service account authentication successful')
        except Exception as e2:
            print(f'Service account failed: {e2}')
            # Final fallback
            try:
                ee.Initialize(project=fallback_project)
                print('Fallback authentication successful')
            except Exception as e3:
                ee.Authenticate()
                ee.Initialize(project=fallback_project)
                print('Interactive authentication completed')


def load_cdl(year, historical_mask, aoi_convexHull, include_confidence=False):
    """Load CDL data for a specific year with optional confidence band"""
    cdl_image = ee.ImageCollection("USDA/NASS/CDL") \
        .filter(ee.Filter.calendarRange(year, year, "year")) \
        .first() \
        .clip(aoi_convexHull)
    
    if include_confidence:
        # Load both cropland and confidence bands (caller has already checked availability)
        cdl_image = cdl_image.select(["cropland", "confidence"])
        cdl_image = cdl_image.updateMask(historical_mask)
        return cdl_image.rename([f"CDL_{year}", f"confidence_{year}"])
    else:
        # Original behavior - cropland only
        cdl_image = cdl_image.select("cropland")
        cdl_image = cdl_image.updateMask(historical_mask)
        return cdl_image.rename(f"CDL_{year}")


def encode_label(image, cdl_classes):
    """Encode crop labels from CDL classes - works with any selected crops"""
    # Start with all pixels as "Other" (0)
    result = image.multiply(0).add(0)
    
    # Apply each selected crop class (skip "Other" since it's default)
    for crop_name, crop_code in cdl_classes.items():
        if crop_name != "Other":
            result = result.where(image.eq(crop_code), crop_code)
    
    return result.rename("crop_label")


def add_rotation_features(history_years, historical_mask, cdl_classes, aoi_convexHull):
    """Add crop rotation features from historical years - dynamic based on selected crops"""
    features = []
    for y in history_years:
        cdl = load_cdl(y, historical_mask, aoi_convexHull)
        # Create rotation features for each selected crop (skip "Other")
        for crop_name, crop_code in cdl_classes.items():
            if crop_name != "Other":
                crop_name_lower = crop_name.lower()
                was_crop = cdl.eq(crop_code).rename(f"was_{crop_name_lower}_{y}")
                features.append(was_crop)
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
    # Use only the crops that are configured, excluding "Other"
    crop_codes = [cdl_classes[crop] for crop in cdl_classes.keys() if crop != "Other"]
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
        }).rename('NDRE2')
    return img.addBands(ndre)


def calculate_crop_areas(image, band_name, cdl_classes, aoi, m2_to_acres, resolution, county_scale_reduction_factor, tileScale):
    """Calculate areas for all selected crops dynamically"""
    aoi_convexHull = aoi.convexHull()
    aoi_fc = ee.FeatureCollection(aoi)
    
    crop_areas = {}
    
    # Calculate area for each selected crop (skip "Other")
    for crop_name, crop_code in cdl_classes.items():
        if crop_name != "Other":
            # Create mask for this crop
            crop_mask = image.eq(crop_code)
            areaImage_clipped = crop_mask.clipToCollection(aoi_fc)
            
            # Calculate area statistics
            stats = areaImage_clipped.reduceRegion(**{
                'reducer': ee.Reducer.sum(),
                'geometry': aoi_convexHull,
                'scale': resolution * county_scale_reduction_factor,
                'maxPixels': 1e13,
                'tileScale': tileScale
            })
            
            # Convert to acres and millions
            Crop_Area_m2 = stats.getInfo()
            Crop_Area_m2 = Crop_Area_m2[band_name]
            Crop_Area_m2 = (Crop_Area_m2 * (resolution * county_scale_reduction_factor) ** 2)
            Crop_Area_acres = Crop_Area_m2 * m2_to_acres
            Crop_Area_millions = round(Crop_Area_acres / 10**6, 3)
            
            crop_areas[crop_name] = Crop_Area_millions
    
    return crop_areas


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
    """Create stratified training points from training image - works with any selected crops"""
    
    # Build classValues dynamically from selected crops
    classValues = [0]  # Always include "Other" class
    for crop_name, crop_code in cdl_classes.items():
        if crop_name != "Other":
            classValues.append(crop_code)
    
    # Sort to ensure consistent order
    classValues.sort()
    
    training_points = training_image.clipToCollection(aoi_fc).stratifiedSample(
        numPoints=0,
        classBand="crop_label",
        classValues=classValues,  # Dynamic based on selected crops
        classPoints=classPoints,   # Correct length array
        region=aoi_convexHull,
        scale=resolution * county_scale_reduction_factor,
        seed=42,
        geometries=False
    )
    return training_points


def apply_confidence_mask(cdl_image, confidence_threshold):
    """
    Apply CDL confidence mask to filter out low-confidence pixels
    
    Args:
        cdl_image: ee.Image with both cropland and confidence bands
        confidence_threshold: Integer (0-100) minimum confidence threshold
        
    Returns:
        ee.Image: CDL image masked to high-confidence pixels only
    """
    # Extract confidence band
    confidence_band = cdl_image.select('confidence.*')
    
    # Create high confidence mask (confidence >= threshold)
    high_confidence_mask = confidence_band.gte(confidence_threshold)
    
    # Apply mask to the CDL image
    masked_cdl = cdl_image.updateMask(high_confidence_mask)
    
    print(f"   🎯 Applied CDL confidence filter: threshold ≥ {confidence_threshold}%")
    
    return masked_cdl


def log_confidence_metrics_to_journal(training_year, confidence_threshold, region_name):
    """Log confidence filtering metrics to conversation journal"""
    from datetime import datetime, timezone, timedelta
    
    # Get current time in local timezone (UTC+3 based on user preference)
    utc_time = datetime.now(timezone.utc)
    local_time = utc_time + timedelta(hours=3)
    timestamp = local_time.strftime('%Y-%m-%d %H:%M:%S')
    
    log_entry = f"""
### CDL Confidence Filtering Applied - {region_name}
**Date:** {timestamp} (Local Time)
- **Training Year:** {training_year}
- **Confidence Threshold:** ≥{confidence_threshold}%
- **Status:** CDL data filtered for high-confidence training points only
- **Effect:** Training will use only pixels where USDA has high confidence in crop classification

"""
    
    try:
        # Use the existing conversation journal path pattern
        journal_path = "/home/jupyter/Tal/Crop_Classifer_for_GIT/12-9-2025/12-9-2025-1854/CONVERSATION_JOURNAL.md"
        with open(journal_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Warning: Could not write to conversation journal: {e}")
        # Still continue with processing


def split_training_points(training_points, split_ratio, seed):
    """
    Split training points into train and validation sets using Google Earth Engine
    
    Args:
        training_points: ee.FeatureCollection of training samples
        split_ratio: Float (0-1) representing training split (e.g., 0.8 = 80% train, 20% validation)
        seed: Integer for reproducible random split
        
    Returns:
        tuple: (train_points, validation_points) as ee.FeatureCollection objects
    """
    # Add random column for splitting
    training_points_with_random = training_points.randomColumn('random', seed)
    
    # Split based on random column threshold
    train_points = training_points_with_random.filter(ee.Filter.lt('random', split_ratio))
    validation_points = training_points_with_random.filter(ee.Filter.gte('random', split_ratio))
    
    return train_points, validation_points


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


def evaluate_validation_performance(classifier, validation_points, feature_stack, cdl_classes):
    """
    Evaluate classifier performance on validation set using LOCAL calculation (no GEE .getInfo() overhead)
    
    Args:
        classifier: Trained ee.Classifier object
        validation_points: ee.FeatureCollection of validation samples
        feature_stack: ee.Image containing all features used for training
        cdl_classes: Dictionary mapping crop names to CDL codes
        
    Returns:
        Dictionary containing validation metrics (pre-calculated, no GEE objects)
    """
    # Classify validation points
    validated = validation_points.classify(classifier)
    
    # SINGLE .getInfo() call to download all validation data at once
    # This gets both ground truth ('crop_label') and predictions ('classification')
    validation_data = validated.getInfo()
    
    # Extract features (each feature is a point with ground truth and prediction)
    features = validation_data['features']
    
    # Initialize counters
    class_correct = {}  # correct predictions per class
    class_total = {}    # total samples per class
    total_correct = 0
    total_samples = len(features)
    
    # Initialize all classes
    for crop_name, class_code in cdl_classes.items():
        class_correct[class_code] = 0
        class_total[class_code] = 0
    
    # Count correct predictions locally (no more GEE calls!)
    for feature in features:
        properties = feature['properties']
        ground_truth = properties['crop_label']
        prediction = properties['classification']
        
        # Count total samples per class
        class_total[ground_truth] = class_total.get(ground_truth, 0) + 1
        
        # Count correct predictions
        if ground_truth == prediction:
            class_correct[ground_truth] = class_correct.get(ground_truth, 0) + 1
            total_correct += 1
    
    # Calculate metrics locally
    overall_accuracy = total_correct / total_samples if total_samples > 0 else 0
    
    # Calculate per-class accuracy
    class_accuracy = {}
    for class_code in cdl_classes.values():
        if class_total.get(class_code, 0) > 0:
            class_accuracy[class_code] = class_correct.get(class_code, 0) / class_total[class_code]
        else:
            class_accuracy[class_code] = 0
    
    # Prepare metrics dictionary (all values are local, no GEE objects!)
    validation_metrics = {
        'overall_accuracy': overall_accuracy,  # Local float value
        'class_accuracy': class_accuracy,      # Local dictionary
        'class_correct': class_correct,        # Local dictionary
        'class_total': class_total,           # Local dictionary
        'total_correct': total_correct,       # Local int
        'total_samples': total_samples,       # Local int
        'cdl_classes': cdl_classes
    }
    
    return validation_metrics


def print_validation_metrics(validation_metrics):
    """
    Print validation performance metrics in a readable format - FAST LOCAL VERSION
    
    Args:
        validation_metrics: Dictionary with local values (no GEE objects)
    """
    print("\n" + "="*60)
    print("🔍 VALIDATION PERFORMANCE METRICS (Fast Local Calculation)")
    print("="*60)
    
    # Overall accuracy (local value, no .getInfo() needed!)
    overall_acc = validation_metrics['overall_accuracy']
    print(f"📊 Overall Accuracy: {overall_acc:.4f} ({overall_acc*100:.2f}%)")
    
    # Sample counts (local values, no .getInfo() needed!)
    class_total = validation_metrics['class_total']
    total_samples = validation_metrics['total_samples']
    
    print(f"\n📈 Validation Sample Counts:")
    for class_code, count in class_total.items():
        if count > 0:  # Only show classes that have samples
            # Find crop name from CDL classes
            crop_name = "Unknown"
            for name, code in validation_metrics['cdl_classes'].items():
                if code == class_code:
                    crop_name = name
                    break
            print(f"   {crop_name} (code {class_code}): {count} samples")
    print(f"   Total: {total_samples} validation samples")
    
    # Per-class accuracy metrics (local calculation, no .getInfo() needed!)
    class_accuracy = validation_metrics['class_accuracy']
    class_correct = validation_metrics['class_correct']
    
    print(f"\n📋 Per-Class Accuracy:")
    print(f"{'Crop':<15} {'Accuracy':<10} {'Correct':<8} {'Total':<8}")
    print("-" * 50)
    
    for class_code, accuracy in class_accuracy.items():
        if class_total.get(class_code, 0) > 0:  # Only show classes with samples
            # Find crop name
            crop_name = "Unknown"
            for name, code in validation_metrics['cdl_classes'].items():
                if code == class_code:
                    crop_name = name
                    break
            
            correct = class_correct.get(class_code, 0)
            total = class_total.get(class_code, 0)
            print(f"{crop_name:<15} {accuracy*100:>7.2f}%   {correct:>6}   {total:>6}")
    
    print("-" * 50)
    print(f"{'OVERALL':<15} {overall_acc*100:>7.2f}%   {validation_metrics['total_correct']:>6}   {total_samples:>6}")
    print("="*60)


def log_validation_metrics_to_journal(validation_metrics, training_year):
    """
    Log validation metrics to CONVERSATION_JOURNAL.md - FAST LOCAL VERSION
    
    Args:
        validation_metrics: Dictionary with local values (no GEE objects)
        training_year: Year used for training
    """
    import datetime
    
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open("CONVERSATION_JOURNAL.md", "a", encoding="utf-8") as f:
            f.write(f"\n## Validation Performance Metrics (Fast Local) - {timestamp}\n")
            f.write(f"**Training Year:** {training_year}\n\n")
            
            # Overall accuracy (local value, no .getInfo()!)
            overall_acc = validation_metrics['overall_accuracy']
            f.write(f"**Overall Validation Accuracy:** {overall_acc:.4f} ({overall_acc*100:.2f}%)\n\n")
            
            # Sample counts (local values, no .getInfo()!)
            class_total = validation_metrics['class_total']
            total_samples = validation_metrics['total_samples']
            f.write("**Validation Sample Counts:**\n")
            for class_code, count in class_total.items():
                if count > 0:  # Only log classes with samples
                    # Find crop name from CDL classes
                    crop_name = "Unknown"
                    for name, code in validation_metrics['cdl_classes'].items():
                        if code == class_code:
                            crop_name = name
                            break
                    f.write(f"- {crop_name} (code {class_code}): {count} samples\n")
            f.write(f"- **Total:** {total_samples} validation samples\n\n")
            
            # Per-class accuracy (local values, no .getInfo()!)
            class_accuracy = validation_metrics['class_accuracy']
            class_correct = validation_metrics['class_correct']
            
            f.write("**Per-Class Performance:**\n")
            f.write("| Crop | Accuracy | Correct | Total |\n")
            f.write("|------|----------|---------|-------|\n")
            
            for class_code, accuracy in class_accuracy.items():
                if class_total.get(class_code, 0) > 0:  # Only show classes with samples
                    # Find crop name
                    crop_name = "Unknown"
                    for name, code in validation_metrics['cdl_classes'].items():
                        if code == class_code:
                            crop_name = name
                            break
                    
                    correct = class_correct.get(class_code, 0)
                    total = class_total.get(class_code, 0)
                    f.write(f"| {crop_name} | {accuracy*100:.2f}% | {correct} | {total} |\n")
            
            f.write(f"| **OVERALL** | **{overall_acc*100:.2f}%** | **{validation_metrics['total_correct']}** | **{total_samples}** |\n")
            f.write("\n---\n")
            
    except Exception as e:
        print(f"⚠️  Could not log validation metrics to journal: {e}")


def calculate_errors_vs_usda(results_dict, usda_data_dict, year, crops_to_process):
    """
    Calculate errors between model predictions and USDA reference data for selected crops
    
    Args:
        results_dict: Dictionary with state names as keys and prediction results as values
        usda_data_dict: Dictionary with crop names as keys and USDA data dictionaries as values
        year: Year for which to get USDA data
        crops_to_process: List of crops being processed
        
    Returns:
        Dictionary with error statistics per state and overall
    """
    # Initialize error results structure dynamically for selected crops
    error_results = {
        'per_state': {},
        'overall': {}
    }
    
    # Initialize overall structure for each crop
    for crop in crops_to_process:
        crop_lower = crop.lower()
        error_results['overall'][crop_lower] = {
            'total_predicted': 0, 'total_usda': 0, 'states_with_data': 0, 'states_missing_data': []
        }
    
    for state_name, predictions in results_dict.items():
        state_errors = {}
        
        # Process each selected crop
        for crop in crops_to_process:
            crop_lower = crop.lower()
            state_errors[crop_lower] = {}
            
            # Get predictions (already in million acres)
            crop_pred = predictions.get(crop, 0)
            
            # Get USDA reference data
            crop_usda = None
            if crop in usda_data_dict:
                usda_data = usda_data_dict[crop]
                if state_name in usda_data and year in usda_data[state_name]:
                    crop_usda = usda_data[state_name][year]
            
            # Calculate errors
            if crop_usda is not None:
                crop_error = crop_pred - crop_usda
                crop_error_pct = (crop_error / crop_usda * 100) if crop_usda != 0 else 0
                crop_abs_error_pct = abs(crop_error_pct)
                
                state_errors[crop_lower] = {
                    'predicted': crop_pred,
                    'usda': crop_usda,
                    'error': crop_error,
                    'error_pct': crop_error_pct,
                    'abs_error_pct': crop_abs_error_pct
                }
                
                # Add to overall totals
                error_results['overall'][crop_lower]['total_predicted'] += crop_pred
                error_results['overall'][crop_lower]['total_usda'] += crop_usda
                error_results['overall'][crop_lower]['states_with_data'] += 1
            else:
                state_errors[crop_lower] = {'error': 'No USDA data available'}
                error_results['overall'][crop_lower]['states_missing_data'].append(state_name)
                
        error_results['per_state'][state_name] = state_errors
    
    # Calculate overall error statistics for each crop
    for crop in crops_to_process:
        crop_lower = crop.lower()
        overall = error_results['overall'][crop_lower]
        if overall['total_usda'] > 0:
            overall['total_error'] = overall['total_predicted'] - overall['total_usda']
            overall['total_error_pct'] = (overall['total_error'] / overall['total_usda']) * 100
            overall['total_abs_error_pct'] = abs(overall['total_error_pct'])
        
    return error_results


def print_error_report(error_results, year):
    """Print formatted error report for any selected crops"""
    print(f"\n{'='*80}")
    print(f"ERROR ANALYSIS vs USDA DATA for {year}")
    print('='*80)
    
    # Get list of crops from the error results
    crops_processed = list(error_results['overall'].keys())
    
    # Per state errors
    print("\nPER STATE ERRORS:")
    print("-" * 80)
    print(f"{'State':<15} {'Crop':<10} {'Predicted':<10} {'USDA':<10} {'Error':<8} {'Error %':<10}")
    print("-" * 80)
    
    for state_name, errors in error_results['per_state'].items():
        for crop in crops_processed:
            if crop in errors:
                crop_errors = errors[crop]
                if isinstance(crop_errors, dict) and 'error' in crop_errors:
                    if crop_errors['error'] == 'No USDA data available':
                        print(f"{state_name:<15} {crop.upper():<10} {'N/A':<10} {'N/A':<10} {'No data':<8} {'N/A':<10}")
                    else:
                        print(f"{state_name:<15} {crop.upper():<10} {crop_errors['predicted']:<10.3f} {crop_errors['usda']:<10.3f} {crop_errors['error']:<8.3f} {crop_errors['error_pct']:<10.1f}%")
    
    # Overall statistics
    print(f"\n{'='*80}")
    print("OVERALL STATISTICS:")
    print('='*80)
    
    for crop in crops_processed:
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


def sanitize_state_name_for_asset(state_name):
    """Sanitize state name for use in asset ID"""
    return state_name.replace(" ", "_").replace("-", "_")


def export_classification_to_asset(classified_image, aoi_convex_hull, state, year, 
                                 asset_project='satyield-algo', asset_folder='tal_satyield'):
    """Export classification image to Earth Engine asset - matches working 28-8 reference"""
    try:
        from datetime import datetime
        import time
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_state = sanitize_state_name_for_asset(state)
        # Use exact same hardcoded path as working 28-8 reference
        asset_id = f"projects/satyield-algo/assets/tal_satyield/{sanitized_state}_{year}_Crop_Classification_{timestamp}"
        
        # Export to Earth Engine asset - exact same parameters as 28-8 reference
        export_task = ee.batch.Export.image.toAsset(
            image=classified_image,
            description=f"{state}_{year}_classification",
            assetId=asset_id,
            scale=300,
            crs='EPSG:4326',
            region=aoi_convex_hull,
            maxPixels=1e13
        )
        export_task.start()
        print(f"Classification export started. Asset ID: {asset_id}")
        
        # Monitor export task progress
        print("\n📤 Monitoring export task progress...")
        while export_task.active():
            print(f'   🔄 Export in progress (task id: {export_task.id})')
            time.sleep(5)  # Check every 5 seconds
        
        # Check final status
        status = export_task.status()
        if status['state'] == 'COMPLETED':
            print(f'   ✅ Export completed successfully!')
            return asset_id
        else:
            print(f'   ❌ Export failed with state: {status["state"]}')
            if 'error_message' in status:
                print(f'   Error: {status["error_message"]}')
            return None
    except Exception as e:
        print(f"   ❌ Error exporting classification: {str(e)}")
        return None