# Crop Classifier - Revised Version

This is the refactored version of the crop classifier with separated configuration and functions.

## Structure

```
revised/
├── config.py              # All parameters and configuration
├── crop_functions.py       # All core functions
├── main.py                # Main execution script
├── anvilcloudmegpai-29e62c9d27e3.json  # Service account credentials
└── README.md              # This file
```

## Files Description

### config.py
Contains all configuration parameters:
- Model parameters (year, dates, features)
- Spatial resolution settings
- XGBoost parameters
- State lists
- Authentication settings

### crop_functions.py
Contains all core functions:
- Earth Engine initialization
- Data loading (CDL, Sentinel-2)
- Feature engineering (rotation features, satellite indices)
- Classification and area calculation functions

### main.py
Main orchestration script that:
- Imports config and functions
- Runs the full classification workflow
- Handles failed states and retries
- Outputs final results

## Usage

```bash
cd 9-9-2025/revised
python main.py
```

## Configuration

To modify parameters, edit `config.py`:
- Change `selected_year` to predict different years
- Modify `features_to_use` to use different satellite features
- Adjust `use_satellite_data` to enable/disable satellite features
- Update state lists or extrapolation factors as needed

## Benefits of This Structure

1. **Maintainability**: Parameters are centralized in config.py
2. **Reusability**: Functions can be imported and used separately
3. **Testability**: Individual functions can be tested in isolation
4. **Clarity**: Main workflow is clear and readable
5. **Flexibility**: Easy to modify parameters without touching core logic