import 'dart:io';
import '../models/media_item.dart';
import 'google_drive_service.dart';

/// Service for loading local media files from the cache directory
class LocalFileService {
  final String _cacheDir;

  LocalFileService({String? cacheDir}) : _cacheDir = cacheDir ?? './media';

  /// Get cache directory path
  String get cacheDir => _cacheDir;

  /// Initialize cache directory
  Future<void> initCacheDirectory() async {
    final cacheDirObj = Directory(_cacheDir);
    if (!await cacheDirObj.exists()) {
      await cacheDirObj.create(recursive: true);
    }
  }

  /// Scan local directory for media files
  Future<List<MediaItem>> scanLocalFiles(List<String> supportedFormats) async {
    final List<MediaItem> items = [];

    try {
      final cacheDirObj = Directory(_cacheDir);

      if (!await cacheDirObj.exists()) {
        return items;
      }

      // List all files in the directory
      final entities = await cacheDirObj.list().toList();

      for (final entity in entities) {
        if (entity is File) {
          final path = entity.path;
          final name = entity.uri.pathSegments.last;

          // Get file extension
          final dotIndex = name.lastIndexOf('.');
          final ext = dotIndex != -1 ? name.substring(dotIndex).toLowerCase() : '';

          // Check if file is supported
          if (!supportedFormats.contains(ext)) {
            continue;
          }

          // Get file stats
          final stat = await entity.stat();

          // Determine if video
          final isVideo = ['.mp4', '.avi', '.mov', '.mkv', '.webm'].contains(ext);

          // Create a MediaItem for local file
          // Use filename as ID for local files
          final id = name.hashCode.toString();

          items.add(MediaItem(
            id: id,
            name: name,
            downloadUrl: null, // No download URL for local files
            webContentLink: null,
            modifiedTime: stat.modified,
            fileSize: stat.size,
            mimeType: isVideo ? 'video/$ext' : 'image/$ext',
            thumbnailLink: null,
            localPath: path,
            isVideo: isVideo,
            isDownloaded: true, // Local files are always "downloaded"
          ));
        }
      }

      // Sort by modified time (newest first)
      items.sort((a, b) {
        if (a.modifiedTime == null || b.modifiedTime == null) return 0;
        return b.modifiedTime!.compareTo(a.modifiedTime!);
      });

    } catch (e) {
      throw Exception('Error scanning local files: $e');
    }

    return items;
  }

  /// Check if a file exists locally
  Future<bool> fileExists(String path) async {
    final file = File(path);
    return await file.exists();
  }
}
