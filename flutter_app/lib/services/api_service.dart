import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

/// API Service for communicating with Python backend
///
/// The Python backend runs as a local HTTP server and provides:
/// - Media sync from Google Drive
/// - Hardware detection
/// - Settings management
/// - Slideshow control
class ApiService {
  // Default backend URL (localhost for bundled Python, or remote IP)
  String _baseUrl = 'http://localhost:8080';

  String get baseUrl => _baseUrl;

  void setBaseUrl(String url) {
    _baseUrl = url.replaceAll(RegExp(r'/+$'), '');
  }

  /// Check if Python backend is running
  Future<bool> checkConnection() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/api/health'))
          .timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Get hardware information
  Future<Map<String, dynamic>> getHardwareInfo() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/hardware'));
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
    throw Exception('Failed to get hardware info');
  }

  /// Get current settings
  Future<Map<String, dynamic>> getSettings() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/settings'));
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
    throw Exception('Failed to get settings');
  }

  /// Update settings
  Future<void> updateSettings(Map<String, dynamic> settings) async {
    final response = await http.put(
      Uri.parse('$_baseUrl/api/settings'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode(settings),
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to update settings');
    }
  }

  /// Start Google Drive sync
  Future<Map<String, dynamic>> startSync() async {
    final response = await http.post(Uri.parse('$_baseUrl/api/sync/start'));
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
    throw Exception('Failed to start sync');
  }

  /// Get sync status
  Future<Map<String, dynamic>> getSyncStatus() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/sync/status'));
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
    throw Exception('Failed to get sync status');
  }

  /// Get media list
  Future<List<Map<String, dynamic>>> getMediaList() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/media'));
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.cast<Map<String, dynamic>>();
    }
    throw Exception('Failed to get media list');
  }

  /// Start slideshow
  Future<void> startSlideshow() async {
    final response = await http.post(Uri.parse('$_baseUrl/api/slideshow/start'));
    if (response.statusCode != 200) {
      throw Exception('Failed to start slideshow');
    }
  }

  /// Stop slideshow
  Future<void> stopSlideshow() async {
    final response = await http.post(Uri.parse('$_baseUrl/api/slideshow/stop'));
    if (response.statusCode != 200) {
      throw Exception('Failed to stop slideshow');
    }
  }

  /// Get slideshow status
  Future<Map<String, dynamic>> getSlideshowStatus() async {
    final response = await http.get(Uri.parse('$_baseUrl/api/slideshow/status'));
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
    throw Exception('Failed to get slideshow status');
  }

  /// Get media file URL
  String getMediaUrl(String filename) {
    return '$_baseUrl/media/$filename';
  }

  /// Next media item
  Future<void> nextMedia() async {
    await http.post(Uri.parse('$_baseUrl/api/slideshow/next'));
  }

  /// Previous media item
  Future<void> previousMedia() async {
    await http.post(Uri.parse('$_baseUrl/api/slideshow/previous'));
  }
}
