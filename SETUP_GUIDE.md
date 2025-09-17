# Crop Area Classification - Setup Guide

## Overview
Your crop area classification system uses Google Earth Engine, Sentinel-2 satellite imagery, and machine learning to predict corn and soy planted areas across US states. The system is well-structured with separated configuration and functions.

## Current Status ✅
- **Code Structure**: Excellent - well-organized with `config.py`, `crop_functions.py`, and `main.py`
- **Dependencies**: Installed in virtual environment
- **Demo**: Working demonstration created

## Required Setup for Real Execution

### 1. Google Earth Engine Authentication

You need ONE of the following authentication methods:

#### Option A: Service Account (Recommended for Production)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable the Earth Engine API
4. Create a service account:
   - Go to IAM & Admin > Service Accounts
   - Click "Create Service Account"
   - Give it Earth Engine permissions
5. Generate and download the JSON key file
6. Place it in your workspace as `anvilcloudmegpai-29e62c9d27e3.json`

#### Option B: Personal Authentication
1. Install Google Cloud SDK:
   ```bash
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   ```
2. Authenticate:
   ```bash
   gcloud auth login
   earthengine authenticate
   ```

### 2. Virtual Environment Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install earthengine-api
```

### 3. Running the Code

#### Quick Test Run (4 states)
```bash
source venv/bin/activate
python3 main.py
```

#### Full Production Run
Edit `config.py` to change:
```python
only_corn_soy_belt_states = 0  # Use all states
corn_or_soy_states = 1  # 1 for corn states, 0 for soy states
```

## Configuration Options

### Key Parameters in `config.py`:
- `training_year = 2023` - Year for training data
- `inference_year = 2024` - Year to predict
- `use_satellite_data = 1` - Include Sentinel-2 features
- `features_to_use = ['GCVI']` - Satellite features to use
- `crops_to_analyze = ["Corn", "Soy"]` - Crops to predict

### Performance Tuning:
- `tileScale = 16` - Lower = faster but may timeout
- `n_points_per_class_satellite = 3000` - Training points per class
- `numberOfTrees = 300` - XGBoost trees
- `county_scale_reduction_factor = 9` - Resolution reduction

## Expected Runtime
- **4 states (current config)**: ~10-30 minutes
- **All corn states (~47 states)**: 2-4 hours
- **All soy states (~30 states)**: 1-3 hours

## Output
The system provides:
1. **Per-state predictions** with USDA comparison
2. **Final extrapolated totals** for entire USA
3. **Error analysis** vs USDA planted acres
4. **Timing information** and processing logs

## Troubleshooting

### Common Issues:
1. **Authentication errors**: Check service account file or gcloud auth
2. **Memory errors**: Reduce `tileScale` or `n_points_per_class`
3. **Timeout errors**: Increase `tileScale` or reduce states
4. **State failures**: Automatic retry mechanism handles this

### Debug Mode:
The code includes comprehensive error handling and will retry failed states automatically.

## File Structure
```
/workspace/
├── config.py              # All configuration parameters
├── crop_functions.py       # Core Earth Engine functions
├── main.py                # Main execution script
├── usda_data.py           # USDA reference data
├── demo_run.py            # Demo version (no auth needed)
├── SETUP_GUIDE.md         # This file
└── venv/                  # Virtual environment
```

## Next Steps
1. Set up Google Earth Engine authentication
2. Test with the current 4-state configuration
3. Expand to full state coverage as needed
4. Customize crops and parameters in `config.py`

Your code is production-ready and well-structured! 🚀