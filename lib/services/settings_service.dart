import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
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

  /// Resolve file: prefix to actual URL from file
  Future<String> _resolveFileUrl(String urlOrPath) async {
    if (urlOrPath.startsWith('file:')) {
      final filePath = urlOrPath.substring(5); // Remove 'file:' prefix
      try {
        final file = File(filePath);
        if (await file.exists()) {
          final content = await file.readAsString();
          return content.trim();
        }
      } catch (e) {
        debugPrint('[SettingsService] Failed to read URL from $filePath: $e');
      }
    }
    return urlOrPath;
  }

  /// Load settings from file with fallback to project directory
  Future<AppSettings> loadSettings() async {
    // Try multiple locations in order
    final pathsToTry = <String>[];

    // 1. Application documents directory
    try {
      final directory = await getApplicationDocumentsDirectory();
      pathsToTry.add('${directory.path}/$_settingsFileName');
    } catch (e) {
      // Ignore
    }

    // 2. Current working directory
    pathsToTry.add('./$_settingsFileName');

    for (final path in pathsToTry) {
      try {
        final file = File(path);
        if (await file.exists()) {
          final contents = await file.readAsString();
          final json = jsonDecode(contents) as Map<String, dynamic>;

          // Resolve file: prefix for google_drive_url
          if (json['google_drive_url'] is String) {
            final resolvedUrl = await _resolveFileUrl(json['google_drive_url'] as String);
            json['google_drive_url'] = resolvedUrl;
          }

          debugPrint('[SettingsService] Loaded settings from: $path');
          debugPrint('[SettingsService] googleDriveUrl: ${json['google_drive_url']}');

          return AppSettings.fromJson(json);
        }
      } catch (e) {
        debugPrint('[SettingsService] Failed to load $path: $e');
      }
    }

    debugPrint('[SettingsService] Using default settings');
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
