import 'dart:convert';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import '../models/app_settings.dart';

/// Service for managing application settings
class SettingsService {
  static const String _settingsFileName = 'settings.json';
  String? _settingsPath;

  SettingsService();

  Future<String> get _localPath async {
    if (_settingsPath != null) return _settingsPath!;
    
    try {
      final directory = await getApplicationDocumentsDirectory();
      _settingsPath = '${directory.path}/$_settingsFileName';
      return _settingsPath!;
    } catch (e) {
      _settingsPath = './$_settingsFileName';
      return _settingsPath!;
    }
  }

  /// Load settings from file
  Future<AppSettings> loadSettings() async {
    try {
      final path = await _localPath;
      final file = File(path);
      
      if (await file.exists()) {
        final contents = await file.readAsString();
        return AppSettings.fromJsonString(contents);
      }
    } catch (e) {
      // Return default settings on error
    }
    return AppSettings();
  }

  /// Save settings to file
  Future<void> saveSettings(AppSettings settings) async {
    try {
      final path = await _localPath;
      final file = File(path);
      await file.writeAsString(settings.toJsonString(), flush: true);
    } catch (e) {
      throw Exception('Failed to save settings: $e');
    }
  }

  /// Reset settings to defaults
  Future<void> resetSettings() async {
    await saveSettings(AppSettings());
  }

  /// Check if settings file exists
  Future<bool> settingsExists() async {
    final path = await _localPath;
    return File(path).exists();
  }

  /// Export settings to a specific path
  Future<void> exportSettings(AppSettings settings, String exportPath) async {
    final file = File(exportPath);
    await file.writeAsString(settings.toJsonString(), flush: true);
  }

  /// Import settings from a specific path
  Future<AppSettings> importSettings(String importPath) async {
    final file = File(importPath);
    if (!await file.exists()) {
      throw Exception('Settings file not found: $importPath');
    }
    final contents = await file.readAsString();
    return AppSettings.fromJsonString(contents);
  }

  /// Get settings as JSON string for debugging
  Future<String> getSettingsJson() async {
    final settings = await loadSettings();
    return const JsonEncoder.withIndent('  ').convert(settings.toJson());
  }
}
