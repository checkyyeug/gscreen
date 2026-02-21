import 'dart:convert';

/// Application settings model
class AppSettings {
  // Google Drive (not used in local-only mode)
  final String googleDriveUrl;  // Kept for compatibility, but should be empty
  final List<String> supportedFormats;