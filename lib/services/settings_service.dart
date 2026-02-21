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
  /// Tries multiple locations to find the URL file
  Future<String> _resolveFileUrl(String urlOrPath, String settingsDir) async {
    if (!urlOrPath.startsWith('file:')) {
      return urlOrPath;
    }

    final filePath = urlOrPath.substring(5); // Remove 'file:' prefix

    // List of paths to try for the URL file
    final pathsToTry = <String>[];

    // 1. Relative to settings file directory
    pathsToTry.add(p.join(settingsDir, filePath));

    // 2. Relative to current working directory
    pathsToTry.add(filePath);

    // 3. Try project directory (parent of settings if settings is in a subfolder)
    final cwd = Directory.current.path;
    pathsToTry.add(p.join(cwd, filePath));

    // 4. Try Documents folder
    try {
      final docsDir = await getApplicationDocumentsDirectory();
      pathsToTry.add(p.join(docsDir.path, filePath));
    } catch (e) {
      // Ignore
    }

    for (final path in pathsToTry) {
      try {
        final file = File(path);
        if (await file.exists()) {
          final content = await file.readAsString();
          final url = content.trim();
          debugPrint('[SettingsService] Loaded URL from: $path');
          debugPrint('[SettingsService] URL: $url');
          return url;
        }
      } catch (e) {
        debugPrint('[SettingsService] Failed to read $path: $e');
      }
    }

    debugPrint('[SettingsService] Could not find URL file, tried: $pathsToTry');
    return urlOrPath; // Return original if file not found
  }

  /// Load settings from file with fallback to project directory
  Future<AppSettings> loadSettings() async {
    // List of (settings_path, base_dir) tuples
    // base_dir is used to resolve relative file: paths
    final locationsToTry = <({String path, String baseDir})>[];

    // 1. Application documents directory
    try {
      final directory = await getApplicationDocumentsDirectory();
      locationsToTry.add((
        path: '${directory.path}/$_settingsFileName',
        baseDir: directory.path
      ));
    } catch (e) {
      // Ignore
    }

    // 2. Current working directory
    locationsToTry.add((
      path: './$_settingsFileName',
      baseDir: Directory.current.path
    ));

    for (final location in locationsToTry) {
      try {
        final file = File(location.path);
        if (await file.exists()) {
          final contents = await file.readAsString();
          final json = jsonDecode(contents) as Map<String, dynamic>;

          // Resolve file: prefix for google_drive_url
          if (json['google_drive_url'] is String) {
            final rawUrl = json['google_drive_url'] as String;
            final resolvedUrl = await _resolveFileUrl(rawUrl, location.baseDir);
            json['google_drive_url'] = resolvedUrl;
          }

          debugPrint('[SettingsService] Loaded settings from: ${location.path}');
          return AppSettings.fromJson(json);
        }
      } catch (e) {
        debugPrint('[SettingsService] Failed to load ${location.path}: $e');
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
