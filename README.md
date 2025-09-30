# CSI Application - WiFi Channel State Information System

## Overview
This application is a comprehensive Channel State Information (CSI) system for WiFi-based human detection and counting using ESP32 devices. The system consists of a React Native mobile app (CSI App), Flask backend API, and data processing utilities for real-time CSI data collection, analysis, and visualization.

## Dataset Access

The dataset is available upon request for research purposes only.  
👉 Please fill this form: [Request Dataset Access](https://forms.gle/xxxx)

## System Architecture

### Components
1. **ESP32 WiFi CSI Device** - Hardware sensor for CSI data collection
2. **Flask Backend API** - Data processing and storage server
3. **React Native App (CSIApp)** - Mobile interface for data visualization
4. **Data Processing Utils** - Analysis and visualization tools
5. **IP Webcam Integration** - Video recording synchronized with CSI data

## Installation & Setup

### Backend Setup (Flask API)

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run the Flask server:**
```bash
python api/route.py
```
The server will start on `http://localhost:5001`

### Frontend Setup (React Native App)

1. **Navigate to CSIApp directory:**
```bash
cd CSIApp
```

2. **Install dependencies:**
```bash
npm install
```

3. **Install Expo CLI (if not installed):**
```bash
npm install -g @expo/cli
```

4. **Configure API endpoint:**
Create a `.env` file in CSIApp directory:
```env
EXPO_PUBLIC_API_HOST=YOUR_COMPUTER_IP
EXPO_PUBLIC_API_PORT=5001
EXPO_PUBLIC_API_TIMEOUT=10000
```

5. **Update IP configuration:**
```bash
npm run update-ip
```

6. **Start the development server:**
```bash
npm start
# or for specific platforms:
npm run android  # For Android
npm run ios      # For iOS
npm run web      # For web browser
```

## Data Collection Process

### 1. WiFi Network Configuration

**Network Topology:**
All devices must connect to the same WiFi network for proper communication:

```
WiFi Router (Gateway)
├── ESP32 CSI Device (e.g., 192.168.1.101)
├── Laptop/Computer (Flask Server) (e.g., 192.168.1.100:5001)
├── Android Device (IP Webcam) (e.g., 192.168.1.102:8080)
└── Mobile Device (Expo App) (e.g., 192.168.1.103)
```

**For ESP32 CSI Device:**
- Connect ESP32 to your WiFi network
- Configure the device to send CSI data to your computer's IP address
- Ensure ESP32 and computer can communicate (ping test recommended)

**For Laptop/Computer (Flask Server):**
- Connect to the same WiFi network as ESP32
- Note your computer's IP address: `ipconfig` (Windows) or `ifconfig` (Mac/Linux)
- Ensure firewall allows connections on port 5001

**For Mobile Devices:**
- Expo development device: Connect to same WiFi network
- IP Webcam device: Connect to same WiFi network
- Test network connectivity between all devices

**Network Requirements:**
- Stable WiFi connection for all devices
- All devices on same subnet (usually 192.168.1.x)
- Open UDP/TCP ports for data transmission
- Firewall configured to allow local network communication

### 2. CSI Data Collection Flow

```
ESP32 Device → WiFi CSI Data → Flask API → Data Storage → Mobile App Visualization
```

**Process:**
1. ESP32 continuously collects CSI data from WiFi signals
2. Data is transmitted via UDP/TCP to Flask backend
3. Flask API processes and stores data in CSV/JSON format
4. Mobile app fetches processed data for real-time visualization
5. Optional: IP Webcam records synchronized video

### 3. IP Webcam Setup

**Network Configuration:**
- **Android device (IP Webcam)**: Connect to WiFi network
- **Laptop (Flask server)**: Connect to the same WiFi network
- **Mobile device (Expo app)**: Connect to the same WiFi network
- All devices must be on the same WiFi subnet for communication

**For Android devices:**
1. Install IP Webcam app from Google Play Store
2. Connect Android device to your WiFi network
3. Configure video settings (resolution, framerate)
4. Start IP Webcam server
5. Note the IP address and port displayed (usually :8080)
6. Example: `192.168.1.102:8080`

**Network Setup Example:**
```
WiFi Router: 192.168.1.1
├── Android (IP Webcam): 192.168.1.102:8080
├── Laptop (Flask Server): 192.168.1.100:5001
└── Mobile (Expo App): 192.168.1.103
```

**Configure in CSI App:**
- Open CSI App settings
- Enter IP Webcam address: `192.168.1.102`
- Enter port: `8080`
- Test connection before starting data collection

**Integration with CSI data:**
- Video recording starts/stops with CSI collection
- Timestamps are synchronized between video and CSI data
- Combined data useful for ground truth validation

### 4. Data Storage Structure

When running the system, the following data folders are created:

```
data/
├── csi_raw/           # Raw CSI data from ESP32
│   ├── session_YYYYMMDD_HHMMSS.csv
│   └── ...
├── processed/         # Processed CSI data
│   ├── amplitude/     # CSI amplitude data
│   ├── phase/         # CSI phase data
│   └── features/      # Extracted features
├── videos/           # IP Webcam recordings
│   ├── session_YYYYMMDD_HHMMSS.mp4
│   └── ...
├── visualizations/   # Generated plots and charts
│   ├── heatmaps/
│   ├── time_series/
│   └── spectrograms/
└── logs/            # System logs
    ├── api_logs/
    └── device_logs/
```

### 5. Environment Configuration

**Backend Environment:**
```bash
# Set Python path if needed
export PYTHONPATH="${PYTHONPATH}:/path/to/Multi-CSI-Frame-App"

# Configure data directory
export CSI_DATA_DIR="/path/to/data/storage"

# Set Flask environment
export FLASK_ENV=development
export FLASK_DEBUG=1
```

**Frontend Environment (.env file in CSIApp/):**
```env
# API Configuration - IP của laptop chạy Flask server
EXPO_PUBLIC_API_HOST=192.168.1.100
EXPO_PUBLIC_API_PORT=5001
EXPO_PUBLIC_API_TIMEOUT=10000

# IP Webcam Configuration - IP của máy Android chạy IP Webcam
EXPO_PUBLIC_WEBCAM_HOST=192.168.1.102
EXPO_PUBLIC_WEBCAM_PORT=8080

# Data Collection Settings
EXPO_PUBLIC_COLLECTION_INTERVAL=100
EXPO_PUBLIC_BUFFER_SIZE=1000
```

**Network Setup Commands:**
```bash
# Check your computer's IP (Mac/Linux)
ifconfig | grep "inet " | grep -v 127.0.0.1

# Check your computer's IP (Windows)
ipconfig | findstr "IPv4"

# Test connection to IP Webcam
curl http://192.168.1.102:8080

# Test connection to Flask server
curl http://192.168.1.100:5001/api/status
```

## Usage

### Starting Data Collection

1. **Start Flask Backend:**
```bash
python api/route.py
```

2. **Power on ESP32 device** and ensure WiFi connection

3. **Launch CSI App:**
```bash
cd CSIApp && npm start
```

4. **Optional: Start IP Webcam** on Android device

5. **Begin Collection:**
   - Open CSI App on mobile device
   - Navigate to "Data Collection" screen
   - Configure collection parameters
   - Press "Start Collection"
   - Monitor real-time data visualization

### Data Analysis

**Using Built-in Utilities:**
```bash
# Analyze collected data
python utils/analyze_data.py --input data/csi_raw/session_*.csv

# Generate visualizations
python visualize/visualize.py --data data/processed/

# Create video from frames
python utils/generate_video_from_frames.py --input data/visualizations/
```

## Features

### Mobile App (CSIApp)
- Real-time CSI data visualization
- Data collection control
- Network configuration
- File management and export
- Debug information display
- IP Webcam integration

### Backend API
- CSI data processing and storage
- Real-time data streaming
- File management endpoints
- Data analysis APIs
- Video synchronization
- Device communication

### Data Processing
- CSI amplitude/phase extraction
- Noise filtering and smoothing
- Feature extraction for ML
- Visualization generation
- Video frame extraction
- Statistical analysis

## Technology Stack

**Frontend (React Native):**
- Expo SDK ~53.0.20
- React Navigation 7.x
- TypeScript
- React Native Chart Kit
- Axios for API communication

**Backend (Flask):**
- Flask 3.0+
- Flask-CORS
- NumPy, Pandas for data processing
- Matplotlib, Seaborn for visualization
- PySerial for device communication
- PyTorch for ML processing

**Hardware:**
- ESP32 WiFi modules
- Android devices (for IP Webcam)
- WiFi router/access point

## Troubleshooting

### Common Issues

**Connection Problems:**
- Ensure all devices are on same WiFi network
- Check firewall settings on computer
- Verify IP addresses in configuration files

**Data Collection Issues:**
- Check ESP32 power and WiFi connection
- Verify Flask server is running and accessible
- Monitor logs in `data/logs/` directory

**App Performance:**
- Close other apps to free memory
- Check network stability
- Reduce visualization update frequency

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is for research purposes only. Please cite appropriately if used in academic work.

## Contact

For questions or support, please open an issue in the repository.
