import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import '../models/media_item.dart';

/// Service for syncing media from Google Drive
class GoogleDriveService {
  static const String _driveApiBase = 'https://www.googleapis.com/drive/v3';
  static const String _driveDownloadBase = 'https://www.googleapis.com/drive/v3/files';

  String? _accessToken;
  String? _folderId;
  String _cacheDir = './media';

  GoogleDriveService();

  void setAccessToken(String token) {
    _accessToken = token;
  }

  void setFolderId(String folderId) {
    _folderId = folderId;
  }

  Future<void> initCacheDirectory() async {
    try {
      final directory = await getApplicationDocumentsDirectory();
      _cacheDir = '${directory.path}/media';
      final cacheDir = Directory(_cacheDir);
      if (!await cacheDir.exists()) {
        await cacheDir.create(recursive: true);
      }
    } catch (e) {
      _cacheDir = './media';
    }
  }

  String get cacheDir => _cacheDir;

  /// Extract folder ID from Google Drive URL
  String? extractFolderId(String url) {
    // Handle URLs like:
    // https://drive.google.com/drive/folders/YOUR_FOLDER_ID
    // https://drive.google.com/open?id=YOUR_FOLDER_ID
    final folderMatch = RegExp(r'/folders/([a-zA-Z0-9_-]+)').firstMatch(url);
    if (folderMatch != null) {
      return folderMatch.group(1);
    }
    final idMatch = RegExp(r'[?&]id=([a-zA-Z0-9_-]+)').firstMatch(url);
    if (idMatch != null) {
      return idMatch.group(1);
    }
    return null;
  }

  /// Fetch list of files from Google Drive folder
  Future<List<MediaItem>> fetchFiles() async {
    if (_accessToken == null || _folderId == null) {
      throw Exception('Access token or folder ID not set');
    }

    final List<MediaItem> items = [];

    try {
      // Get files in the folder
      final response = await http.get(
        Uri.parse(
          '$_driveApiBase/files?q="$_folderId"+in+parents+and+trashed=false'
          '&fields=files(id,name,mimeType,modifiedTime,fileSize,thumbnailLink,webContentLink)',
        ),
        headers: {'Authorization': 'Bearer $_accessToken'},
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to fetch files: ${response.body}');
      }

      // Parse JSON properly
      final Map<String, dynamic> data = jsonDecode(response.body);
      final List<dynamic> files = data['files'] as List<dynamic>? ?? [];

      for (final file in files) {
        final fileMap = file as Map<String, dynamic>;
        final mimeType = fileMap['mimeType'] as String? ?? '';
        final name = fileMap['name'] as String? ?? '';
        final id = fileMap['id'] as String? ?? '';

        // Check if it's a folder (skip)
        if (mimeType == 'application/vnd.google-apps.folder') {
          continue;
        }

        // Check if it's a Google Docs file (skip, can't display directly)
        if (mimeType.startsWith('application/vnd.google-apps.')) {
          continue;
        }

        // Check file extension
        final dotIndex = name.lastIndexOf('.');
        final ext = dotIndex != -1 ? name.substring(dotIndex).toLowerCase() : '';

        // Build download URL
        String? downloadUrl;
        if (!mimeType.startsWith('application/vnd.google-apps.')) {
          downloadUrl = '$_driveDownloadBase/$id?alt=media';
        }

        final isVideo = ['.mp4', '.avi', '.mov', '.mkv', '.webm'].contains(ext);

        items.add(MediaItem(
          id: id,
          name: name,
          downloadUrl: downloadUrl,
          webContentLink: fileMap['webContentLink'] as String?,
          modifiedTime: fileMap['modifiedTime'] != null
              ? DateTime.tryParse(fileMap['modifiedTime'] as String)
              : null,
          fileSize: fileMap['fileSize'] != null
              ? int.tryParse(fileMap['fileSize'] as String)
              : null,
          mimeType: mimeType,
          thumbnailLink: fileMap['thumbnailLink'] as String?,
          localPath: '$_cacheDir/$id$ext',
          isVideo: isVideo,
        ));
      }
    } catch (e) {
      throw Exception('Error fetching Google Drive files: $e');
    }

    return items;
  }

  /// Download a media file
  Future<String> downloadFile(MediaItem item) async {
    if (_accessToken == null) {
      throw Exception('Access token not set');
    }

    final file = File(item.localPath);

    // Check if already downloaded with same size
    if (await file.exists() && item.fileSize != null) {
      final stat = await file.stat();
      if (stat.size == item.fileSize) {
        return item.localPath;
      }
    }

    // Download the file
    try {
      final response = await http.get(
        Uri.parse(item.downloadUrl!),
        headers: {'Authorization': 'Bearer $_accessToken'},
      );

      if (response.statusCode != 200) {
        throw Exception('Failed to download file: ${response.statusCode}');
      }

      await file.writeAsBytes(response.bodyBytes);
      return item.localPath;
    } catch (e) {
      throw Exception('Error downloading file: $e');
    }
  }

  /// Check if a file needs to be downloaded (doesn't exist or size mismatch)
  Future<bool> needsDownload(MediaItem item) async {
    final file = File(item.localPath);
    if (!await file.exists()) return true;
    if (item.fileSize == null) return false;
    final stat = await file.stat();
    return stat.size != item.fileSize;
  }

  /// Incremental sync - only download new/changed files
  Future<List<MediaItem>> syncFiles(List<MediaItem> remoteFiles) async {
    final List<MediaItem> toDownload = [];

    for (final file in remoteFiles) {
      if (await needsDownload(file)) {
        toDownload.add(file);
      }
    }

    return toDownload;
  }

  /// Get supported file extensions from Google Drive
  Future<List<String>> getSupportedExtensions() async {
    return [
      '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
      '.tiff', '.tif', '.tga', '.pbm', '.pgm', '.ppm',
      '.pnm', '.ico', '.pcx', '.dib', '.xbm',
      '.mp4', '.avi', '.mov', '.mkv', '.webm'
    ];
  }
}
