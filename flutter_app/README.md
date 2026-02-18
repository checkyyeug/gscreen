# gScreen Flutter App

Cross-platform UI for gScreen using Flutter.

## Supported Platforms

- Android
- Windows
- Linux
- iOS (experimental)
- macOS (experimental)
- Web (limited functionality)

## Architecture

```
┌─────────────────────────────────────────────┐
│           Flutter UI Layer                  │
│  (Android / Windows / Linux / iOS / macOS) │
├─────────────────────────────────────────────┤
│         Communication Layer                 │
│         (HTTP REST API)                     │
├─────────────────────────────────────────────┤
│           Python Core (Backend)             │
│  - Google Drive Sync                        │
│  - Media Processing                         │
│  - Hardware Detection                       │
└─────────────────────────────────────────────┘
```

## Getting Started

### Prerequisites

1. Install Flutter SDK: https://docs.flutter.dev/get-started/install
2. Install Python 3.8+ with required packages

### Run Python Backend

```bash
cd /path/to/gscreen
python3 api_server.py --port 8080
```

### Run Flutter App

```bash
cd flutter_app
flutter pub get
flutter run
```

### Build for Production

```bash
# Android APK
flutter build apk --release

# Windows
flutter build windows --release

# Linux
flutter build linux --release
```

## Project Structure

```
flutter_app/
├── lib/
│   ├── main.dart           # App entry point
│   ├── screens/            # UI screens
│   │   ├── home_screen.dart
│   │   ├── settings_screen.dart
│   │   └── sync_screen.dart
│   ├── widgets/            # Reusable widgets
│   │   └── status_bar.dart
│   ├── services/           # Business logic
│   │   ├── api_service.dart
│   │   └── settings_service.dart
│   ├── models/             # Data models
│   └── utils/              # Utilities
├── assets/
│   ├── images/
│   └── fonts/
├── web/                    # Web-specific files
└── pubspec.yaml           # Dependencies
```

## API Endpoints

The Python backend provides these REST API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/hardware` | GET | Hardware information |
| `/api/settings` | GET/PUT | Settings management |
| `/api/sync/start` | POST | Start Google Drive sync |
| `/api/sync/status` | GET | Get sync status |
| `/api/media` | GET | Get media list |
| `/api/slideshow/start` | POST | Start slideshow |
| `/api/slideshow/stop` | POST | Stop slideshow |
| `/api/slideshow/status` | GET | Get slideshow status |
| `/media/{filename}` | GET | Get media file |
