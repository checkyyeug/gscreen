import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import '../models/media_item.dart';
import '../models/app_settings.dart';
import '../services/google_drive_service.dart';
import '../services/local_file_service.dart';
import '../services/settings_service.dart';

/// Slideshow state
enum SlideshowState {
  idle,
  loading,
  playing,
  paused,
  error,
  noMedia,
  sleeping,
}

/// Provider for slideshow state and logic
class SlideshowProvider extends ChangeNotifier {
  final GoogleDriveService _driveService;
  final LocalFileService _localFileService;
  final SettingsService _settingsService;

  // State
  SlideshowState _state = SlideshowState.idle;
  List<MediaItem> _mediaItems = [];
  int _currentIndex = 0;
  AppSettings _settings = AppSettings();
  String? _errorMessage;
  Timer? _slideshowTimer;
  bool _isSyncing = false;
  DateTime? _lastSyncTime;
  bool _useLocalFiles = false; // Whether to use local files instead of Drive

  // Countdown
  int _countdownSeconds = 0;
  Timer? _countdownTimer;

  // Getters
  SlideshowState get state => _state;
  List<MediaItem> get mediaItems => _mediaItems;
  int get currentIndex => _currentIndex;
  MediaItem? get currentItem =>
      _mediaItems.isNotEmpty && _currentIndex < _mediaItems.length
          ? _mediaItems[_currentIndex]
          : null;
  AppSettings get settings => _settings;

  set settings(AppSettings newSettings) {
    _settings = newSettings;
    notifyListeners();
  }
  String? get errorMessage => _errorMessage;
  bool get isSyncing => _isSyncing;
  DateTime? get lastSyncTime => _lastSyncTime;
  int get countdownSeconds => _countdownSeconds;
  int get totalItems => _mediaItems.length;
  bool get useLocalFiles => _useLocalFiles;

  // Progress info
  String get progressText =>
      '${_currentIndex + 1} / ${_mediaItems.length}';

  SlideshowProvider({
    GoogleDriveService? driveService,
    LocalFileService? localFileService,
    SettingsService? settingsService,
  })  : _driveService = driveService ?? GoogleDriveService(),
        _localFileService = localFileService ?? LocalFileService(),
        _settingsService = settingsService ?? SettingsService();

  /// Initialize the provider
  Future<void> init() async {
    _state = SlideshowState.loading;
    notifyListeners();

    try {
      // Load settings
      _settings = await _settingsService.loadSettings();
      debugPrint('[SlideshowProvider] Settings loaded, googleDriveUrl: "${_settings.googleDriveUrl}"');

      // Initialize local file service
      await _localFileService.initCacheDirectory();

      // Initialize drive service
      await _driveService.initCacheDirectory();

      // Extract folder ID from URL
      bool hasDriveConfig = false;
      if (_settings.googleDriveUrl.isNotEmpty) {
        final folderId = _driveService.extractFolderId(_settings.googleDriveUrl);
        debugPrint('[SlideshowProvider] Extracted folderId: $folderId');
        if (folderId != null) {
          _driveService.setFolderId(folderId);
          hasDriveConfig = true;
        }
      }

      // Determine if we should use local files (no Drive config)
      _useLocalFiles = !hasDriveConfig;
      debugPrint('[SlideshowProvider] _useLocalFiles: $_useLocalFiles');

      _state = SlideshowState.idle;
      notifyListeners();
    } catch (e) {
      debugPrint('[SlideshowProvider] Init error: $e');
      _state = SlideshowState.error;
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  /// Update settings
  Future<void> updateSettings(AppSettings newSettings) async {
    _settings = newSettings;
    await _settingsService.saveSettings(newSettings);

    // Update folder ID if URL changed
    if (newSettings.googleDriveUrl.isNotEmpty) {
      final folderId = _driveService.extractFolderId(newSettings.googleDriveUrl);
      if (folderId != null) {
        _driveService.setFolderId(folderId);
        _useLocalFiles = false;
      }
    } else {
      _useLocalFiles = true;
    }

    notifyListeners();
  }

  /// Set Google Drive access token
  void setAccessToken(String token) {
    _driveService.setAccessToken(token);
    _useLocalFiles = false;
  }

  /// Start slideshow
  void startSlideshow() {
    if (_mediaItems.isEmpty) {
      _state = SlideshowState.noMedia;
      notifyListeners();
      return;
    }

    _state = SlideshowState.playing;
    _startTimer();
    notifyListeners();
  }

  /// Pause slideshow
  void pauseSlideshow() {
    _state = SlideshowState.paused;
    _stopTimer();
    notifyListeners();
  }

  /// Resume slideshow
  void resumeSlideshow() {
    _state = SlideshowState.playing;
    _startTimer();
    notifyListeners();
  }

  /// Stop slideshow
  void stopSlideshow() {
    _state = SlideshowState.idle;
    _stopTimer();
    _currentIndex = 0;
    notifyListeners();
  }

  /// Go to next media
  void nextMedia() {
    if (_mediaItems.isEmpty) return;

    _currentIndex = (_currentIndex + 1) % _mediaItems.length;
    _resetTimer();
    notifyListeners();
  }

  /// Go to previous media
  void previousMedia() {
    if (_mediaItems.isEmpty) return;

    _currentIndex = (_currentIndex - 1 + _mediaItems.length) % _mediaItems.length;
    _resetTimer();
    notifyListeners();
  }

  /// Skip to specific index
  void skipToIndex(int index) {
    if (index < 0 || index >= _mediaItems.length) return;

    _currentIndex = index;
    _resetTimer();
    notifyListeners();
  }

  /// Start countdown for schedule
  void startCountdown(int seconds) {
    _countdownSeconds = seconds;
    _countdownTimer?.cancel();
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      _countdownSeconds--;
      if (_countdownSeconds <= 0) {
        timer.cancel();
        startSlideshow();
      }
      notifyListeners();
    });
    notifyListeners();
  }

  /// Cancel countdown
  void cancelCountdown() {
    _countdownTimer?.cancel();
    _countdownSeconds = 0;
    notifyListeners();
  }

  /// Check and handle schedule
  void checkSchedule() {
    if (!_settings.schedule.enabled) {
      if (_state == SlideshowState.idle || _state == SlideshowState.sleeping) {
        startSlideshow();
      }
      return;
    }

    if (_settings.schedule.isActiveNow()) {
      if (_state == SlideshowState.sleeping) {
        startSlideshow();
      } else if (_state == SlideshowState.idle) {
        startSlideshow();
      }
    } else {
      // Outside schedule - sleep
      if (_state == SlideshowState.playing || _state == SlideshowState.paused) {
        _state = SlideshowState.sleeping;
        _stopTimer();
        _startCountdownIfNeeded();
        notifyListeners();
      }
    }
  }

  void _startCountdownIfNeeded() {
    if (_state == SlideshowState.idle && _settings.schedule.enabled) {
      final remaining = _settings.schedule.remainingSeconds;
      if (remaining > 0 && remaining <= 60) {
        startCountdown(remaining);
      }
    }
  }

  /// Sync media from Google Drive or local files
  Future<void> syncMedia({bool forceDownload = false}) async {
    if (_isSyncing) return;

    debugPrint('[SlideshowProvider] syncMedia called, _useLocalFiles: $_useLocalFiles');

    _isSyncing = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (_useLocalFiles) {
        // Use local file scanner
        debugPrint('[SlideshowProvider] Using local file scanner');
        _mediaItems = await _localFileService.scanLocalFiles(_settings.supportedFormats);
        debugPrint('[SlideshowProvider] Found ${_mediaItems.length} local files');
      } else {
        // Use Google Drive
        debugPrint('[SlideshowProvider] Using Google Drive');
        final remoteFiles = await _driveService.fetchFiles();

        // Filter supported formats
        _mediaItems = remoteFiles.where((item) {
          final ext = item.extension;
          return _settings.supportedFormats.contains(ext);
        }).toList();

        // Sort by modified time
        _mediaItems.sort((a, b) {
          if (a.modifiedTime == null || b.modifiedTime == null) return 0;
          return b.modifiedTime!.compareTo(a.modifiedTime!);
        });

        // Check local files
        for (int i = 0; i < _mediaItems.length; i++) {
          final item = _mediaItems[i];
          final file = File(item.localPath);
          if (await file.exists()) {
            _mediaItems[i] = item.copyWith(isDownloaded: true);
          }
        }
      }

      _lastSyncTime = DateTime.now();
      _isSyncing = false;

      // Auto-start if enabled
      if (_settings.sync.downloadOnStart && _mediaItems.isNotEmpty) {
        debugPrint('[SlideshowProvider] Auto-starting slideshow with ${_mediaItems.length} items');
        checkSchedule();
      } else if (_mediaItems.isEmpty) {
        debugPrint('[SlideshowProvider] No media found, setting state to noMedia');
        _state = SlideshowState.noMedia;
      }

      notifyListeners();
    } catch (e) {
      debugPrint('[SlideshowProvider] Sync error: $e');
      _isSyncing = false;
      _errorMessage = e.toString();
      _state = SlideshowState.error;
      notifyListeners();
    }
  }

  /// Download current media item (only for Drive files)
  Future<String?> downloadCurrentMedia() async {
    if (currentItem == null) return null;

    // Local files are already "downloaded"
    if (_useLocalFiles || currentItem!.downloadUrl == null) {
      return currentItem!.localPath;
    }

    try {
      return await _driveService.downloadFile(currentItem!);
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return null;
    }
  }

  void _startTimer() {
    _stopTimer();
    _slideshowTimer = Timer.periodic(
      Duration(seconds: _settings.slideshow.intervalSeconds),
      (_) => nextMedia(),
    );
  }

  void _stopTimer() {
    _slideshowTimer?.cancel();
    _slideshowTimer = null;
  }

  void _resetTimer() {
    if (_state == SlideshowState.playing) {
      _startTimer();
    }
  }

  /// Cleanup
  @override
  void dispose() {
    _stopTimer();
    _countdownTimer?.cancel();
    super.dispose();
  }
}
