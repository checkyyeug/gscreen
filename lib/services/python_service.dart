import 'dart:convert';
import 'dart:io';
import 'package:path_provider/path_provider.dart';

/// Service for integrating with Python backend
class PythonService {
  String? _mediaDir;
  String? _settingsPath;
  String? _projectDir;
  Process? _slideshowProcess;

  PythonService();

  /// Initialize paths
  Future<void> init() async {
    // Get the project directory (where main.py is located)
    _projectDir = _getProjectDir();
    
    // Use project directory for media and settings
    _mediaDir = '$_projectDir/media';
    _settingsPath = '$_projectDir/settings.json';

    // Ensure media directory exists
    final mediaDir = Directory(_mediaDir!);
    if (!await mediaDir.exists()) {
      await mediaDir.create(recursive: true);
    }
  }

  String get mediaDir => _mediaDir ?? './media';
  String get settingsPath => _settingsPath ?? 'settings.json';
  String get projectDir => _projectDir ?? '.';

  /// Get project directory - works on both Windows and Linux
  String _getProjectDir() {
    // For a Flutter Windows app running from build folder,
    // the project root is 3 levels up from build/windows/x64/runner/Release/
    // Or we can use the current working directory
    
    // Try to find the project root by looking for main.py
    final cwd = Directory.current.path;
    
    // Check if we're in the build folder
    if (cwd.contains('build')) {
      // Go up to find project root
      var dir = Directory.current;
      for (int i = 0; i < 4; i++) {
        final parent = dir.parent;
        if (parent.path.isEmpty) break;
        dir = parent;
      }
      
      // Check if main.py exists
      if (File('${dir.path}/main.py').existsSync()) {
        return dir.path;
      }
    }
    
    // Fallback: assume cwd is project root
    return cwd;
  }

  /// Run Python sync and return list of local files
  Future<List<Map<String, dynamic>>> syncFromGoogleDrive() async {
    final List<Map<String, dynamic>> items = [];

    try {
      // First check if Python is available
      final pythonOk = await isPythonAvailable();
      if (!pythonOk) {
        print('Python not available');
        return items;
      }

      // Check if settings.json exists
      final settingsFile = File(settingsPath);
      if (!await settingsFile.exists()) {
        print('Settings file not found: $settingsPath');
        return items;
      }

      // Run Python sync script with --sync-only flag
      // This will sync files from Google Drive to local media folder
      final result = await Process.run(
        'python',
        ['main.py', '--sync-only'],
        workingDirectory: projectDir,
        runInShell: true,
      );

      print('Python sync output: ${result.stdout}');
      print('Python sync errors: ${result.stderr}');
      
      if (result.exitCode != 0) {
        print('Python sync failed with exit code: ${result.exitCode}');
      }
    } catch (e) {
      print('Error running Python sync: $e');
    }

    // Scan local media directory for downloaded files
    return await scanLocalMedia();
  }

  /// Scan local media directory for files
  Future<List<Map<String, dynamic>>> scanLocalMedia() async {
    final List<Map<String, dynamic>> items = [];
    
    try {
      final mediaDir = Directory(_mediaDir ?? './media');
      if (!await mediaDir.exists()) {
        print('Media directory does not exist: $_mediaDir');
        return items;
      }

      await for (final entity in mediaDir.list()) {
        if (entity is File) {
          final name = entity.path.split(Platform.pathSeparator).last;
          final ext = name.toLowerCase().split('.').last;
          final isVideo = ['mp4', 'avi', 'mov', 'mkv', 'webm'].contains(ext);
          final isImage = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].contains(ext);

          if (isImage || isVideo) {
            items.add({
              'id': name.hashCode.toString(),
              'name': name,
              'localPath': entity.path,
              'isVideo': isVideo,
              'mimeType': isVideo ? 'video/$ext' : 'image/$ext',
            });
          }
        }
      }
      
      print('Found ${items.length} media files in $_mediaDir');
    } catch (e) {
      print('Error scanning media directory: $e');
    }

    return items;
  }

  /// Check if Python is available
  Future<bool> isPythonAvailable() async {
    try {
      final result = await Process.run(
        Platform.isWindows ? 'python' : 'python3',
        ['--version'],
        runInShell: true,
      );
      print('Python version: ${result.stdout}');
      return result.exitCode == 0;
    } catch (e) {
      print('Python not found: $e');
      return false;
    }
  }

  /// Run the main Python slideshow (blocks until closed)
  Future<void> runSlideshow() async {
    try {
      _slideshowProcess = await Process.start(
        Platform.isWindows ? 'python' : 'python3',
        ['main.py'],
        workingDirectory: projectDir,
        runInShell: true,
      );

      // Forward output
      _slideshowProcess!.stdout.transform(utf8.decoder).listen((data) {
        print('[Python] $data');
      });
      
      _slideshowProcess!.stderr.transform(utf8.decoder).listen((data) {
        print('[Python Error] $data');
      });

      final exitCode = await _slideshowProcess!.exitCode;
      print('Python slideshow exited with code: $exitCode');
    } catch (e) {
      throw Exception('Failed to start Python slideshow: $e');
    }
  }

  /// Run Python slideshow in background (non-blocking)
  Future<void> runSlideshowBackground() async {
    try {
      _slideshowProcess = await Process.start(
        Platform.isWindows ? 'python' : 'python3',
        ['main.py'],
        workingDirectory: projectDir,
        runInShell: true,
        mode: ProcessStartMode.detached,
      );

      print('Started Python slideshow in background, pid: ${_slideshowProcess!.pid}');
    } catch (e) {
      throw Exception('Failed to start Python slideshow: $e');
    }
  }

  /// Stop the running Python slideshow
  void stopSlideshow() {
    _slideshowProcess?.kill();
    _slideshowProcess = null;
  }

  /// Get current settings
  Future<Map<String, dynamic>?> getSettings() async {
    try {
      final file = File(settingsPath);
      if (await file.exists()) {
        final content = await file.readAsString();
        return jsonDecode(content) as Map<String, dynamic>;
      }
    } catch (e) {
      print('Error reading settings: $e');
    }
    return null;
  }

  /// Update settings
  Future<bool> updateSettings(Map<String, dynamic> settings) async {
    try {
      final file = File(settingsPath);
      await file.writeAsString(
        const JsonEncoder.withIndent('  ').convert(settings),
      );
      return true;
    } catch (e) {
      print('Error writing settings: $e');
      return false;
    }
  }

  /// Check Google Drive URL status
  Future<String?> getGoogleDriveUrl() async {
    try {
      final settings = await getSettings();
      if (settings != null) {
        var url = settings['google_drive_url'] as String?;
        
        // Handle file: reference
        if (url != null && url.startsWith('file:')) {
          final urlFile = File('${projectDir}/${url.substring(5)}');
          if (await urlFile.exists()) {
            url = (await urlFile.readAsString()).trim();
          }
        }
        
        return url;
      }
    } catch (e) {
      print('Error getting Google Drive URL: $e');
    }
    return null;
  }

  /// Set Google Drive URL
  Future<bool> setGoogleDriveUrl(String url) async {
    try {
      final settings = await getSettings();
      if (settings != null) {
        settings['google_drive_url'] = url;
        return await updateSettings(settings);
      }
    } catch (e) {
      print('Error setting Google Drive URL: $e');
    }
    return false;
  }
}
