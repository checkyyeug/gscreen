import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import '../models/media_item.dart';

/// Service for loading local media files from the cache directory
class LocalFileService {
  String _cacheDir = './media';

  /// Get cache directory path
  String get cacheDir => _cacheDir;

  /// Initialize cache directory
  Future<void> initCacheDirectory() async {
    try {
      // Use the same directory as GoogleDriveService
      final directory = await getApplicationDocumentsDirectory();
      _cacheDir = p.join(directory.path, 'media');
      final cacheDirObj = Directory(_cacheDir);
      if (!await cacheDirObj.exists()) {
        await cacheDirObj.create(recursive: true);
      }
      debugPrint('[LocalFileService] Cache dir: $_cacheDir');
    } catch (e) {
      // Fallback to relative path
      _cacheDir = './media';
      debugPrint('[LocalFileService] Using fallback: $_cacheDir');
    }
  }

  /// Also try to scan from a fallback directory (for development)
  Future<List<MediaItem>> scanLocalFiles(List<String> supportedFormats) async {
    final List<MediaItem> items = [];

    debugPrint('[LocalFileService] Scanning for local files...');

    // Try primary cache directory first
    debugPrint('[LocalFileService] Trying primary: $_cacheDir');
    items.addAll(await _scanDirectory(_cacheDir, supportedFormats));
    debugPrint('[LocalFileService] Found ${items.length} files in primary');

    // If no files found and in development, try relative ./media directory
    if (items.isEmpty) {
      debugPrint('[LocalFileService] Trying fallback: ./media');
      items.addAll(await _scanDirectory('./media', supportedFormats));
      debugPrint('[LocalFileService] Found ${items.length} files in ./media');
    }

    // If still no files, try current working directory + media
    if (items.isEmpty) {
      final cwd = Directory.current.path;
      final cwdMedia = p.join(cwd, 'media');
      debugPrint('[LocalFileService] Trying CWD: $cwdMedia');
      items.addAll(await _scanDirectory(cwdMedia, supportedFormats));
      debugPrint('[LocalFileService] Found ${items.length} files in CWD/media');
    }

    debugPrint('[LocalFileService] Total files found: ${items.length}');
    return items;
  }

  /// Scan a specific directory for media files
  Future<List<MediaItem>> _scanDirectory(String dirPath, List<String> supportedFormats) async {
    final List<MediaItem> items = [];

    try {
      final cacheDirObj = Directory(dirPath);

      if (!await cacheDirObj.exists()) {
        debugPrint('[LocalFileService] Directory not found: $dirPath');
        return items;
      }

      debugPrint('[LocalFileService] Scanning: $dirPath');

      // List all files in the directory
      final entities = await cacheDirObj.list().toList();
      debugPrint('[LocalFileService] Found ${entities.length} entities');

      for (final entity in entities) {
        if (entity is File) {
          final path = entity.path;
          final name = p.basename(path);

          // Get file extension
          final ext = p.extension(path).toLowerCase();

          debugPrint('[LocalFileService] File: $name (ext: $ext)');

          // Check if file is supported
          if (!supportedFormats.contains(ext)) {
            debugPrint('[LocalFileService] Skipping unsupported: $ext');
            continue;
          }

          // Get file stats
          final stat = await entity.stat();

          // Determine if video
          final isVideo = ['.mp4', '.avi', '.mov', '.mkv', '.webm'].contains(ext);

          // Create a MediaItem for local file
          final id = name.hashCode.toString();

          items.add(MediaItem(
            id: id,
            name: name,
            downloadUrl: null,
            webContentLink: null,
            modifiedTime: stat.modified,
            fileSize: stat.size,
            mimeType: isVideo ? 'video/$ext' : 'image/$ext',
            thumbnailLink: null,
            localPath: path,
            isVideo: isVideo,
            isDownloaded: true,
          ));
          debugPrint('[LocalFileService] Added: $name');
        }
      }

      // Sort by modified time (newest first)
      items.sort((a, b) {
        if (a.modifiedTime == null || b.modifiedTime == null) return 0;
        return b.modifiedTime!.compareTo(a.modifiedTime!);
      });

    } catch (e) {
      // Silently fail for fallback directories
    }

    return items;
  }

  /// Check if a file exists locally
  Future<bool> fileExists(String path) async {
    final file = File(path);
    return await file.exists();
  }
}
