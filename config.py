# -*- coding: utf-8 -*-
"""
Configuration file for Crop Classifier
Contains all parameters and settings for the crop area classification model
"""

# Main Input Parameters
training_year = 2023  # The year to use for training data (CDL labels and satellite data)
inference_year = 2024  # The year we want to predict (inference/prediction year)
selected_year = inference_year  # Backward compatibility - will be deprecated

day_start = '01'  # start day for satellite data
month_start = '05'  # start month for satellite data
day_end = '30'  # end day for satellite data
month_end = '06'  # end month for satellite data

# Model Configuration
use_satellite_data = 1  # if 0 use only crop rotation based features, 1- use also data from sentinel 2 satellite
only_corn_soy_belt_states = 1  # 1- use only top 15 corn/soy belt states, 0 - use full list of states
corn_or_soy_states = 1  # effective only_corn_belt_states = 0. 1- corn top production states, 0- soy top production states

# Spatial Resolution Parameters
resolution = 30  # satellite native resolution
county_scale_reduction_factor = 9  # resolution reduction factor. The effective resolution is: resolution*county_scale_reduction_factor

# Classification Parameters
# Available CDL crop codes - you can add more crops as needed
available_cdl_classes = {
    "Other": 0,      # Everything else (background)
    "Corn": 1,       # Corn
    "Cotton": 2,     # Cotton
    "Sorghum": 4,    # Sorghum
    "Soy": 5,        # Soybeans
    "Wheat": 24,     # Winter Wheat
    "Barley": 22,    # Barley
    "Oats": 28,      # Oats
    "Rice": 3        # Rice
}

# Crops to analyze - modify this list to change which crops are included
crops_to_analyze = ["Corn", "Soy"]  # Add or remove crops as needed

# Build active CDL classes based on crops_to_analyze
cdl_classes = {"Other": 0}  # Always include "Other" as background
for crop in crops_to_analyze:
    if crop in available_cdl_classes:
        cdl_classes[crop] = available_cdl_classes[crop]
    else:
        raise ValueError(f"Crop '{crop}' not found in available_cdl_classes. Available crops: {list(available_cdl_classes.keys())}")

# Conversion Factors
m2_to_acres = 0.000247105  # conversion from m2 to acres

# Cloud Masking Parameters
QA_BAND = 'cs'  # Clouds masking band
CLEAR_THRESHOLD = 0.65  # Clouds masking thresh

# Processing Parameters
tileScale = 16  # number between 1-16. lower is faster but may cause computation timeout

# Crop Rotation Parameters
n_years_rotation_history = 15  # number of previous years used in crop rotation features

# Sampling Parameters
n_points_per_class_satellite = 3000  # number of points to sample per class when USING satellite data
n_points_per_class_no_satellite = 3000  # number of points to sample per class when NOT USING satellite data

# Dynamic class points based on number of active crops
def get_class_points():
    """Get list of sampling points for each class (Other + active crops)"""
    num_classes = len(cdl_classes)  # Other + active crops
    if use_satellite_data == 1:
        return [n_points_per_class_satellite] * num_classes
    else:
        return [n_points_per_class_no_satellite] * num_classes

# XGBoost Parameters
numberOfTrees = 300  # num of trees in Xgboost
maxNodes = 5  # maximum number of nodes in Xgboost
shrinkage = 0.1  # shrinkage (lambda) parameter in Xgboost

# Feature Selection
features_to_use = ['GCVI']  # ['GCVI','DOY'] # ['NDRE2','DOY'] - features to use from satellite
# Available features: DOY - day of year, GCVI - A Green Chlorophyll Vegetation Index, NDRE2 - Normalized Difference Red Edge Index 2
quality_mosaic_band = 'GCVI'  # 'NDRE2' - band used to calculate quality mosaic

# Extrapolation Ratios
corn_extepolation_ratio = 0.8737  # when only_corn_soy_belt_states = 1 we use this factor to extrapolate CORN Area results to all USA CORN states
soy_extepolation_ratio = 0.848   # when only_corn_soy_belt_states = 1 we use this factor to extrapolate SOY Area results to all USA SOY states

# State Lists
corn_soy_belt_states = [
    "Colorado", "Illinois", "Indiana", "Iowa"  # Reduced to 4 states for performance testing
]

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