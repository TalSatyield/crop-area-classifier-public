# 🌽 Crop Area Classifier

A satellite-based machine learning system for classifying and estimating crop areas using Google Earth Engine, Sentinel-2 satellite imagery, and USDA Cropland Data Layer (CDL).

## 🚀 Features

- **Multi-crop classification**: Support for corn, soy, cotton, wheat, and other major crops
- **Satellite integration**: Uses Sentinel-2 imagery for vegetation indices (GCVI, NDRE2)
- **Crop rotation analysis**: Incorporates historical crop rotation patterns
- **State-level processing**: Processes individual states with extrapolation capabilities
- **XGBoost modeling**: Advanced machine learning for accurate classification
- **Area estimation**: Calculates crop areas in acres with statistical confidence

## 📋 Requirements

- Python 3.7+
- Google Earth Engine account
- GEE service account credentials (JSON file)

## 🛠️ Installation

1. Clone this repository:
```bash
git clone https://github.com/satyieldOP/crop-area-classifier-public.git
cd crop-area-classifier-public
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Google Earth Engine:
   - Create a GEE service account
   - Download the JSON credentials file
   - Update `config.py` with your credentials

## ⚙️ Configuration

Edit `config.py` to customize:

- **Years**: `training_year` and `inference_year`
- **Crops**: Modify `crops_to_analyze` list
- **Features**: Choose satellite features in `features_to_use`
- **States**: Select target states in state lists
- **Model**: Adjust XGBoost parameters

## 🚀 Usage

### Basic Usage
```bash
python main.py
```

### Multi-crop Analysis
See `MULTI_CROP_GUIDE.md` for detailed instructions on analyzing multiple crops.

## 📁 Project Structure

```
├── config.py              # Configuration parameters
├── crop_functions.py       # Core processing functions  
├── main.py                # Main execution script
├── usda_data.py           # USDA data integration
├── MULTI_CROP_GUIDE.md    # Multi-crop analysis guide
├── MULTI_CROP_USAGE.md    # Usage examples
└── requirements.txt       # Python dependencies
```

## 🔧 Key Components

### config.py
Centralized configuration for:
- Model parameters and years
- Spatial resolution settings
- Crop classes and features
- Authentication credentials

### crop_functions.py
Core functions for:
- Earth Engine initialization
- Satellite data processing
- Feature engineering
- Classification algorithms
- Area calculations

### main.py
Orchestrates the full workflow:
- Data loading and preprocessing
- Model training and prediction
- State-by-state processing
- Results aggregation

## 📊 Output

The system generates:
- State-level crop area estimates (acres)
- Classification confidence metrics
- Processing logs and statistics
- Optional visualization outputs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋‍♂️ Support

For questions or issues:
- Create an issue on GitHub
- Check the documentation files for detailed usage

## 🎯 About

Developed by [SatYield](https://github.com/satyieldOP) for satellite-based agricultural monitoring and crop area estimation.