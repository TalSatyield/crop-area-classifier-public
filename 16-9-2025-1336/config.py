# -*- coding: utf-8 -*-
"""
Configuration file for Crop Classifier
Contains all parameters and settings for the crop area classification model
"""

# Main Input Parameters
training_year = 2021  # The year to use for training data (CDL labels and satellite data) - 2023 has confidence band
inference_year = 2025  # The year we want to predict (inference/prediction year)
selected_year = inference_year  # Backward compatibility - will be deprecated

day_start = '10'  # start day for satellite data
month_start = '7'  # start month for satellite data
day_end = '9'  # end day for satellite data
month_end = '9'  # end month for satellite data

# Model Configuration
use_satellite_data = 1  # if 0 use only crop rotation based features, 1- use also data from sentinel 2 satellite
only_corn_soy_belt_states = 1  # 1- use only top 15 corn/soy belt states, 0 - use full list of states
corn_or_soy_states = 1  # effective only_corn_belt_states = 0. 1- corn top production states, 0- soy top production states

# Spatial Resolution Parameters
resolution = 30  # satellite native resolution
county_scale_reduction_factor = 9  # resolution reduction factor. The effective resolution is: resolution*county_scale_reduction_factor

# =============================================================================
# SELECTIVE CROP PROCESSING CONFIGURATION
# =============================================================================

# All available crops with their CDL codes
all_available_crops = {
    "Other": 0,
    "Corn": 1, 
    "Cotton": 2,
    "Rice": 3,
    "Sorghum": 4,
    "Soy": 5,
    "Sunflower": 6,
    "Barley": 21,
    "Spring_Wheat": 23,
    "Winter_Wheat": 24,
    "Oats": 28,
    "Hay": 37
}

# SELECT which crops to process in this run
# Examples: 
# ["Corn", "Soy"] - current setup (same runtime)
# ["Corn"] - corn only (faster)
# ["Wheat"] - wheat only (faster) 
# ["Corn", "Soy", "Wheat"] - three crops (longer)

#crops_to_process = ["Corn", "Soy","Spring_Wheat","Sorghum" ]  # DEFAULT: same as current
crops_to_process = ["Corn", "Soy","Sorghum"]  # DEFAULT: same as current
#crops_to_process = ["Corn", "Soy"]  # DEFAULT: same as current

# Automatically generate cdl_classes from selection
cdl_classes = {"Other": 0}
for crop in crops_to_process:
    if crop in all_available_crops:
        cdl_classes[crop] = all_available_crops[crop]

# Validation: Check selected crops are available
invalid_crops = [crop for crop in crops_to_process if crop not in all_available_crops]
if invalid_crops:
    raise ValueError(f"Invalid crops selected: {invalid_crops}. Available: {list(all_available_crops.keys())[1:]}")

# Classification Parameters (derived from selection above)

# Conversion Factors
m2_to_acres = 0.000247105  # conversion from m2 to acres

# Cloud Masking Parameters
QA_BAND = 'cs'  # Clouds masking band
CLEAR_THRESHOLD = 0.65  # Clouds masking thresh

# Processing Parameters
tileScale = 16  # number between 1-16. lower is faster but may cause computation timeout

# Crop Rotation Parameters
n_years_rotation_history = 20  # number of previous years used in crop rotation features

# Sampling Parameters
n_points_per_class_satellite = 2000  # number of points to sample per class when USING satellite data
n_points_per_class_no_satellite = 2000  # number of points to sample per class when NOT USING satellite data

# XGBoost Parameters
numberOfTrees = 300  # num of trees in Xgboost
maxNodes = 5  # maximum number of nodes in Xgboost
shrinkage = 0.1  # shrinkage (lambda) parameter in Xgboost

# Train/Validation Split Parameters
enable_validation = True  # Enable train/validation split and performance evaluation
train_validation_split = 0.8  # Training split ratio (0.8 = 80% train, 20% validation)
validation_seed = 42  # Random seed for reproducible train/validation splits

# CDL Confidence Filtering Parameters
enable_cdl_confidence_filtering = True  # Enable filtering training data by CDL confidence
cdl_confidence_threshold = 85  # Minimum CDL confidence (0-100 scale) for training points

# Feature Selection
features_to_use = ['GCVI']  # ['GCVI','DOY'] # ['NDRE2','DOY'] - features to use from satellite  
# Available features: DOY - day of year, GCVI - A Green Chlorophyll Vegetation Index, NDRE2 - Normalized Difference Red Edge Index 2
quality_mosaic_band = 'GCVI'  # Use NDRE2 for quality mosaic (now properly computed)

# Extrapolation Ratios
corn_extepolation_ratio = 0.8737  # when only_corn_soy_belt_states = 1 we use this factor to extrapolate CORN Area results to all USA CORN states
soy_extepolation_ratio = 0.848   # when only_corn_soy_belt_states = 1 we use this factor to extrapolate SOY Area results to all USA SOY states

#State Lists
# corn_soy_belt_states = [
#    "South Dakota"  # Test with Illinois - major corn state
# ]

corn_soy_belt_states = ["Colorado","Illinois","Indiana","Iowa","Kansas","Kentucky","Michigan","Minnesota","Missouri",\
               "Nebraska", "North Dakota","Ohio", "Pennsylvania", "South Dakota", "Wisconsin"]

# corn_soy_belt_states = ["Iowa","Kansas","Kentucky","Michigan","Minnesota","Missouri",\
#                "Nebraska", "North Dakota","Pennsylvania", "South Dakota"]

corn_states_list = [
    "Alabama", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", 
    "Florida", "Georgia", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", 
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", 
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", 
    "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", 
    "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", 
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"
]

soy_states_list = [
    "Alabama", "Arkansas", "Delaware", "Georgia", "Illinois", "Indiana", "Iowa", "Kansas", 
    "Kentucky", "Louisiana", "Maryland", "Michigan", "Minnesota", "Mississippi", "Missouri", 
    "Nebraska", "New Jersey", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", 
    "Pennsylvania", "South Carolina", "South Dakota", "Tennessee", "Texas", "Virginia", "Wisconsin"
]

# Calculated Parameters
def get_calculated_parameters():
    """Calculate derived parameters based on base configuration"""
    pixel_area_m2 = (resolution * county_scale_reduction_factor) * (resolution * county_scale_reduction_factor)
    
    if only_corn_soy_belt_states == 1:
        states_to_use = corn_soy_belt_states
        exterpolation_factor_corn = corn_extepolation_ratio
        exterpolation_factor_soy = soy_extepolation_ratio
    else:
        exterpolation_factor_corn = 1
        exterpolation_factor_soy = 1
        if corn_or_soy_states == 1:
            states_to_use = corn_states_list
        else:
            states_to_use = soy_states_list
    
    return {
        'pixel_area_m2': pixel_area_m2,
        'states_to_use': states_to_use,
        'exterpolation_factor_corn': exterpolation_factor_corn,
        'exterpolation_factor_soy': exterpolation_factor_soy,
        'training_year': training_year,
        'inference_year': inference_year
    }

# Authentication
SERVICE_ACCOUNT_FILE = 'anvilcloudmegpai-29e62c9d27e3.json'
GEE_PROJECT = 'anvilcloudmegpai'
FALLBACK_PROJECT = 'ee-odperry'

# Export Configuration
export_classification = True  # Enabled for asset export testing
export_asset_project = 'satyield-algo'  # GEE project for asset exports (matching working 28-8 reference)
export_asset_folder = 'tal_satyield'  # Asset folder within the project (matching working 28-8 reference)

# =============================================================================
# IMAGING AND EXPORT PARAMETERS
# =============================================================================

# Export resolution in meters for testing coarser resolution
export_resolution = 100  # 1000m for coarse resolution testing (vs 300m production)