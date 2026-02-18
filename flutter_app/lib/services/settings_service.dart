import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'api_service.dart';

class SettingsService extends ChangeNotifier {
  final ApiService _apiService;

  // Local settings (cached)
  String _backendUrl = 'http://localhost:8080';
  bool _autoStart = true;
  bool _keepScreenOn = true;
  double _volume = 50.0;

  // Remote settings (from Python backend)
  Map<String, dynamic> _remoteSettings = {};

  SettingsService({ApiService? apiService})
      : _apiService = apiService ?? ApiService() {
    _loadLocalSettings();
  }

  // Getters
  String get backendUrl => _backendUrl;
  bool get autoStart => _autoStart;
  bool get keepScreenOn => _keepScreenOn;
  double get volume => _volume;
  Map<String, dynamic> get remoteSettings => _remoteSettings;

  // Display settings
  int get hdmiPort => _remoteSettings['display']?['hdmi_port'] ?? 1;
  bool get fullscreen => _remoteSettings['display']?['fullscreen'] ?? true;
  String get scaleMode => _remoteSettings['slideshow']?['scale_mode'] ?? 'fit';
  int get rotation => _remoteSettings['display']?['rotation'] ?? 0;
  String get hwAccel => _remoteSettings['display']?['hw_accel'] ?? 'auto';

  // Audio settings
  bool get audioEnabled => _remoteSettings['audio']?['enabled'] ?? false;
  String get audioDevice => _remoteSettings['audio']?['device'] ?? 'hdmi';

  // Sync settings
  String get googleDriveUrl => _remoteSettings['google_drive_url'] ?? '';
  int get syncInterval => _remoteSettings['sync']?['check_interval_minutes'] ?? 1;

  // Schedule settings
  bool get scheduleEnabled => _remoteSettings['schedule']?['enabled'] ?? false;
  String get scheduleStart => _remoteSettings['schedule']?['start'] ?? '07:00';
  String get scheduleStop => _remoteSettings['schedule']?['stop'] ?? '23:00';

  /// Load local settings from SharedPreferences
  Future<void> _loadLocalSettings() async {
    final prefs = await SharedPreferences.getInstance();
    _backendUrl = prefs.getString('backend_url') ?? 'http://localhost:8080';
    _autoStart = prefs.getBool('auto_start') ?? true;
    _keepScreenOn = prefs.getBool('keep_screen_on') ?? true;
    _volume = prefs.getDouble('volume') ?? 50.0;

    _apiService.setBaseUrl(_backendUrl);
    notifyListeners();
  }

  /// Save local settings
  Future<void> _saveLocalSettings() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('backend_url', _backendUrl);
    await prefs.setBool('auto_start', _autoStart);
    await prefs.setBool('keep_screen_on', _keepScreenOn);
    await prefs.setDouble('volume', _volume);
  }

  /// Load remote settings from Python backend
  Future<void> loadRemoteSettings() async {
    try {
      _remoteSettings = await _apiService.getSettings();
      notifyListeners();
    } catch (e) {
      debugPrint('Failed to load remote settings: $e');
    }
  }

  /// Update remote settings
  Future<void> updateRemoteSettings(Map<String, dynamic> settings) async {
    try {
      await _apiService.updateSettings(settings);
      _remoteSettings = settings;
      notifyListeners();
    } catch (e) {
      debugPrint('Failed to update remote settings: $e');
      rethrow;
    }
  }

  // Local settings setters
  void setBackendUrl(String url) {
    _backendUrl = url;
    _apiService.setBaseUrl(url);
    _saveLocalSettings();
    notifyListeners();
  }

  void setAutoStart(bool value) {
    _autoStart = value;
    _saveLocalSettings();
    notifyListeners();
  }

  void setKeepScreenOn(bool value) {
    _keepScreenOn = value;
    _saveLocalSettings();
    notifyListeners();
  }

  void setVolume(double value) {
    _volume = value;
    _saveLocalSettings();
    notifyListeners();
  }
}
