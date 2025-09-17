# Multi-Crop Support Guide

## Overview
The crop classifier now supports multiple crops with minimal changes to the existing workflow. You can easily add or remove crops by modifying the configuration file.

## How to Use Multi-Crop Support

### 1. Basic Configuration
In `config.py`, modify the `crops_to_analyze` list to include the crops you want:

```python
# Example configurations:

# Default: Corn and Soy only
crops_to_analyze = ["Corn", "Soy"]

# Add Sorghum
crops_to_analyze = ["Corn", "Soy", "Sorghum"]

# More crops (when you have USDA data)
crops_to_analyze = ["Corn", "Soy", "Sorghum", "Wheat", "Cotton"]
```

### 2. Available Crop Types
The system currently supports these CDL crop codes:
- **Corn**: CDL code 1
- **Cotton**: CDL code 2
- **Rice**: CDL code 3
- **Sorghum**: CDL code 4
- **Soy**: CDL code 5
- **Barley**: CDL code 22
- **Wheat**: CDL code 24
- **Oats**: CDL code 28

### 3. USDA Reference Data
Currently available USDA reference data for validation:
- ✅ **Corn**: All major corn-producing states (2019-2025)
- ✅ **Soy**: All major soy-producing states (2019-2025)
- ✅ **Sorghum**: Major sorghum states: TX, KS, CO, OK, NE, LA, AR, NM (2019-2025)
- ❌ **Other crops**: USDA data not yet added (contributions welcome!)

### 4. Running the Model

No changes needed to your main workflow! The system automatically:
- Creates training points for all selected crops
- Trains the classifier with the correct number of classes
- Calculates areas for all crops
- Reports results for each crop
- Compares with USDA data when available

```bash
python main.py
```

### 5. Output Format

**Per-State Results** (example with 3 crops):
```
📍 Kansas:
   CORN   : Pred= 6.50M | USDA= 6.30M | Error=+3.2%
   SOY    : Pred= 4.60M | USDA= 4.53M | Error=+1.5%
   SORGHUM: Pred= 2.70M | USDA= 2.60M | Error=+3.8%
```

**Final Results**:
```
🎯 FINAL RESULTS:
Corn Area (million acres): 85.4
Soy Area (million acres): 89.2
Sorghum Area (million acres): 12.1
```

**USDA Validation**:
```
📊 VALIDATION vs USDA DATA (2024):
CORN   : Predicted= 85.4M acres | USDA= 83.2M acres | Error=+2.6%
SOY    : Predicted= 89.2M acres | USDA= 87.5M acres | Error=+1.9%
SORGHUM: Predicted= 12.1M acres | USDA= 11.8M acres | Error=+2.5%
```

## Key Features

### ✅ **Backward Compatibility**
- Existing 2-crop workflows continue to work unchanged
- Original function names still available as wrappers

### ✅ **Dynamic Scaling**
- Training points automatically adjust to number of crops
- Memory and processing scale appropriately

### ✅ **Flexible Configuration**
- Easy to add/remove crops without code changes
- Extensible USDA data structure

### ✅ **Robust Error Handling**
- Graceful handling of missing USDA data
- Clear reporting of data availability per crop

## Adding New Crops

### 1. Find CDL Code
Look up the crop's CDL code from USDA NASS documentation

### 2. Add to Configuration
Add the crop to `available_cdl_classes` in `config.py`:
```python
available_cdl_classes = {
    # ... existing crops ...
    "NewCrop": XX,  # Replace XX with actual CDL code
}
```

### 3. Include in Analysis
Add to `crops_to_analyze`:
```python
crops_to_analyze = ["Corn", "Soy", "NewCrop"]
```

### 4. Add USDA Data (Optional)
Create USDA reference data in `usda_data.py`:
```python
USDA_NEWCROP_PLANTED_ACRES = {
    'StateName': {2019: X.XX, 2020: X.XX, ...},
    # ... more states ...
}
```

And update the USDA data lookup in `main.py`.

## Technical Details

### Modified Functions
- `encode_label()`: Dynamic crop encoding
- `add_rotation_features()`: Multi-crop rotation features  
- `calculate_crop_areas()`: Generic area calculation
- `create_training_points()`: Variable class handling
- `calculate_errors_vs_usda_multi_crop()`: Multi-crop validation

### New Configuration Variables
- `available_cdl_classes`: All supported crop codes
- `crops_to_analyze`: Active crops for current run
- `get_class_points()`: Dynamic sampling points

### Performance Impact
- Training time scales with number of crops (more classes)
- Memory usage increases slightly with more rotation features
- Processing time per state remains similar

## Next Steps

Ready for **Phase 2: Hyperparameter Optimization**!
- 80-20 train-validation split
- Random/Grid search optimization
- Validation-based model selection
