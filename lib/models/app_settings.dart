import 'dart:convert';

/// Application settings model
class AppSettings {
  // Google Drive
  final String googleDriveUrl;
  final List<String> supportedFormats;

  // Display
  final DisplaySettings display;

  // Slideshow
  final SlideshowSettings slideshow;

  // Schedule
  final ScheduleSettings schedule;

  // Audio
  final AudioSettings audio;

  // Sync
  final SyncSettings sync;

  // System
  final SystemSettings system;

  AppSettings({
    this.googleDriveUrl = '',
    List<String>? supportedFormats,
    DisplaySettings? display,
    SlideshowSettings? slideshow,
    ScheduleSettings? schedule,
    AudioSettings? audio,
    SyncSettings? sync,
    SystemSettings? system,
  })  : supportedFormats = supportedFormats ?? _defaultSupportedFormats,
        display = display ?? DisplaySettings(),
        slideshow = slideshow ?? SlideshowSettings(),
        schedule = schedule ?? ScheduleSettings(),
        audio = audio ?? AudioSettings(),
        sync = sync ?? SyncSettings(),
        system = system ?? SystemSettings();

  static const List<String> _defaultSupportedFormats = [
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.tiff', '.tif', '.tga', '.pbm', '.pgm', '.ppm',
    '.pnm', '.ico', '.pcx', '.dib', '.xbm',
    '.mp4', '.avi', '.mov', '.mkv', '.webm'
  ];

  Map<String, dynamic> toJson() {
    return {
      'google_drive_url': googleDriveUrl,
      'supported_formats': supportedFormats,
      'display': display.toJson(),
      'slideshow': slideshow.toJson(),
      'schedule': schedule.toJson(),
      'audio': audio.toJson(),
      'sync': sync.toJson(),
      'system': system.toJson(),
    };
  }

  factory AppSettings.fromJson(Map<String, dynamic> json) {
    return AppSettings(
      googleDriveUrl: json['google_drive_url'] as String? ?? '',
      supportedFormats: (json['supported_formats'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          _defaultSupportedFormats,
      display: json['display'] != null
          ? DisplaySettings.fromJson(json['display'] as Map<String, dynamic>)
          : null,
      slideshow: json['slideshow'] != null
          ? SlideshowSettings.fromJson(json['slideshow'] as Map<String, dynamic>)
          : null,
      schedule: json['schedule'] != null
          ? ScheduleSettings.fromJson(json['schedule'] as Map<String, dynamic>)
          : null,
      audio: json['audio'] != null
          ? AudioSettings.fromJson(json['audio'] as Map<String, dynamic>)
          : null,
      sync: json['sync'] != null
          ? SyncSettings.fromJson(json['sync'] as Map<String, dynamic>)
          : null,
      system: json['system'] != null
          ? SystemSettings.fromJson(json['system'] as Map<String, dynamic>)
          : null,
    );
  }

  String toJsonString() => jsonEncode(toJson());

  factory AppSettings.fromJsonString(String jsonString) {
    return AppSettings.fromJson(jsonDecode(jsonString) as Map<String, dynamic>);
  }

  AppSettings copyWith({
    String? googleDriveUrl,
    List<String>? supportedFormats,
    DisplaySettings? display,
    SlideshowSettings? slideshow,
    ScheduleSettings? schedule,
    AudioSettings? audio,
    SyncSettings? sync,
    SystemSettings? system,
  }) {
    return AppSettings(
      googleDriveUrl: googleDriveUrl ?? this.googleDriveUrl,
      supportedFormats: supportedFormats ?? this.supportedFormats,
      display: display ?? this.display,
      slideshow: slideshow ?? this.slideshow,
      schedule: schedule ?? this.schedule,
      audio: audio ?? this.audio,
      sync: sync ?? this.sync,
      system: system ?? this.system,
    );
  }
}

class DisplaySettings {
  final int hdmiPort;
  final bool fullscreen;
  final bool borderless;
  final List<int> backgroundColor;
  final bool hideMouse;
  final bool showStatusbar;
  final int rotation;
  final String rotationMode;
  final String hwAccel;
  final StatusbarLayoutSettings statusbarLayout;

  DisplaySettings({
    this.hdmiPort = 1,
    this.fullscreen = true,
    this.borderless = true,
    List<int>? backgroundColor,
    this.hideMouse = true,
    this.showStatusbar = true,
    this.rotation = 0,
    this.rotationMode = 'software',
    this.hwAccel = 'auto',
    StatusbarLayoutSettings? statusbarLayout,
  })  : backgroundColor = backgroundColor ?? [0, 0, 0],
        statusbarLayout = statusbarLayout ?? StatusbarLayoutSettings();

  Map<String, dynamic> toJson() {
    return {
      'hdmi_port': hdmiPort,
      'fullscreen': fullscreen,
      'borderless': borderless,
      'background_color': backgroundColor,
      'hide_mouse': hideMouse,
      'show_statusbar': showStatusbar,
      'rotation': rotation,
      'rotation_mode': rotationMode,
      'hw_accel': hwAccel,
      'statusbar_layout': statusbarLayout.toJson(),
    };
  }

  factory DisplaySettings.fromJson(Map<String, dynamic> json) {
    return DisplaySettings(
      hdmiPort: json['hdmi_port'] as int? ?? 1,
      fullscreen: json['fullscreen'] as bool? ?? true,
      borderless: json['borderless'] as bool? ?? true,
      backgroundColor: (json['background_color'] as List<dynamic>?)
          ?.map((e) => e as int)
          .toList(),
      hideMouse: json['hide_mouse'] as bool? ?? true,
      showStatusbar: json['show_statusbar'] as bool? ?? true,
      rotation: json['rotation'] as int? ?? 0,
      rotationMode: json['rotation_mode'] as String? ?? 'software',
      hwAccel: json['hw_accel'] as String? ?? 'auto',
      statusbarLayout: json['statusbar_layout'] != null
          ? StatusbarLayoutSettings.fromJson(
              json['statusbar_layout'] as Map<String, dynamic>)
          : null,
    );
  }

  DisplaySettings copyWith({
    int? hdmiPort,
    bool? fullscreen,
    bool? borderless,
    List<int>? backgroundColor,
    bool? hideMouse,
    bool? showStatusbar,
    int? rotation,
    String? rotationMode,
    String? hwAccel,
    StatusbarLayoutSettings? statusbarLayout,
  }) {
    return DisplaySettings(
      hdmiPort: hdmiPort ?? this.hdmiPort,
      fullscreen: fullscreen ?? this.fullscreen,
      borderless: borderless ?? this.borderless,
      backgroundColor: backgroundColor ?? this.backgroundColor,
      hideMouse: hideMouse ?? this.hideMouse,
      showStatusbar: showStatusbar ?? this.showStatusbar,
      rotation: rotation ?? this.rotation,
      rotationMode: rotationMode ?? this.rotationMode,
      hwAccel: hwAccel ?? this.hwAccel,
      statusbarLayout: statusbarLayout ?? this.statusbarLayout,
    );
  }
}

class StatusbarLayoutSettings {
  final double opacity;
  final OrientationLayout landscape;
  final OrientationLayout portrait;

  StatusbarLayoutSettings({
    this.opacity = 0.3,
    OrientationLayout? landscape,
    OrientationLayout? portrait,
  })  : landscape = landscape ?? OrientationLayout(),
        portrait = portrait ?? OrientationLayout();

  Map<String, dynamic> toJson() {
    return {
      'opacity': opacity,
      'landscape': landscape.toJson(),
      'portrait': portrait.toJson(),
    };
  }

  factory StatusbarLayoutSettings.fromJson(Map<String, dynamic> json) {
    return StatusbarLayoutSettings(
      opacity: (json['opacity'] as num?)?.toDouble() ?? 0.3,
      landscape: json['landscape'] != null
          ? OrientationLayout.fromJson(json['landscape'] as Map<String, dynamic>)
          : null,
      portrait: json['portrait'] != null
          ? OrientationLayout.fromJson(json['portrait'] as Map<String, dynamic>)
          : null,
    );
  }
}

class OrientationLayout {
  final String fileInfoPosition;
  final String systemInfoPosition;
  final String progressPosition;

  OrientationLayout({
    this.fileInfoPosition = 'bottom',
    this.systemInfoPosition = 'bottom',
    this.progressPosition = 'bottom',
  });

  Map<String, dynamic> toJson() {
    return {
      'file_info_position': fileInfoPosition,
      'system_info_position': systemInfoPosition,
      'progress_position': progressPosition,
    };
  }

  factory OrientationLayout.fromJson(Map<String, dynamic> json) {
    return OrientationLayout(
      fileInfoPosition: json['file_info_position'] as String? ?? 'bottom',
      systemInfoPosition: json['system_info_position'] as String? ?? 'bottom',
      progressPosition: json['progress_position'] as String? ?? 'bottom',
    );
  }
}

class SlideshowSettings {
  final int intervalSeconds;
  final String scaleMode;

  SlideshowSettings({
    this.intervalSeconds = 5,
    this.scaleMode = 'fit',
  });

  Map<String, dynamic> toJson() {
    return {
      'interval_seconds': intervalSeconds,
      'scale_mode': scaleMode,
    };
  }

  factory SlideshowSettings.fromJson(Map<String, dynamic> json) {
    return SlideshowSettings(
      intervalSeconds: json['interval_seconds'] as int? ?? 5,
      scaleMode: json['scale_mode'] as String? ?? 'fit',
    );
  }

  SlideshowSettings copyWith({
    int? intervalSeconds,
    String? scaleMode,
  }) {
    return SlideshowSettings(
      intervalSeconds: intervalSeconds ?? this.intervalSeconds,
      scaleMode: scaleMode ?? this.scaleMode,
    );
  }
}

class ScheduleSettings {
  final bool enabled;
  final List<String> days;
  final String start;
  final String stop;

  ScheduleSettings({
    this.enabled = false,
    List<String>? days,
    this.start = '07:00',
    this.stop = '23:00',
  }) : days = days ?? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  Map<String, dynamic> toJson() {
    return {
      'enabled': enabled,
      'days': days,
      'start': start,
      'stop': stop,
    };
  }

  factory ScheduleSettings.fromJson(Map<String, dynamic> json) {
    return ScheduleSettings(
      enabled: json['enabled'] as bool? ?? false,
      days: (json['days'] as List<dynamic>?)?.map((e) => e as String).toList(),
      start: json['start'] as String? ?? '07:00',
      stop: json['stop'] as String? ?? '23:00',
    );
  }

  bool isActiveNow() {
    if (!enabled) return true;

    final now = DateTime.now();
    final dayName = _getDayName(now.weekday);
    if (!days.contains(dayName)) return false;

    final currentMinutes = now.hour * 60 + now.minute;
    final startParts = start.split(':');
    final stopParts = stop.split(':');

    final startMinutes = int.parse(startParts[0]) * 60 + int.parse(startParts[1]);
    final stopMinutes = int.parse(stopParts[0]) * 60 + int.parse(stopParts[1]);

    if (startMinutes <= stopMinutes) {
      return currentMinutes >= startMinutes && currentMinutes < stopMinutes;
    } else {
      // Overnight schedule
      return currentMinutes >= startMinutes || currentMinutes < stopMinutes;
    }
  }

  String _getDayName(int weekday) {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    return days[weekday - 1];
  }

  int get remainingSeconds {
    if (!enabled) return 0;

    final now = DateTime.now();
    final currentMinutes = now.hour * 60 + now.minute;
    final startParts = start.split(':');
    final stopParts = stop.split(':');

    final startMinutes = int.parse(startParts[0]) * 60 + int.parse(startParts[1]);
    final stopMinutes = int.parse(stopParts[0]) * 60 + int.parse(stopParts[1]);

    if (startMinutes <= stopMinutes) {
      if (currentMinutes >= startMinutes && currentMinutes < stopMinutes) {
        return 0; // Within schedule
      }
      int targetMinutes;
      if (currentMinutes < startMinutes) {
        targetMinutes = startMinutes;
      } else {
        targetMinutes = startMinutes + 24 * 60;
      }
      return (targetMinutes - currentMinutes) * 60 - now.second;
    } else {
      if (currentMinutes >= startMinutes || currentMinutes < stopMinutes) {
        return 0;
      }
      int targetMinutes = currentMinutes < stopMinutes ? stopMinutes : stopMinutes + 24 * 60;
      return (targetMinutes - currentMinutes) * 60 - now.second;
    }
  }

  ScheduleSettings copyWith({
    bool? enabled,
    List<String>? days,
    String? start,
    String? stop,
  }) {
    return ScheduleSettings(
      enabled: enabled ?? this.enabled,
      days: days ?? this.days,
      start: start ?? this.start,
      stop: stop ?? this.stop,
    );
  }
}

class AudioSettings {
  final bool enabled;
  final String device;
  final int volume;

  AudioSettings({
    this.enabled = false,
    this.device = 'hdmi',
    this.volume = 50,
  });

  Map<String, dynamic> toJson() {
    return {
      'enabled': enabled,
      'device': device,
      'volume': volume,
    };
  }

  factory AudioSettings.fromJson(Map<String, dynamic> json) {
    return AudioSettings(
      enabled: json['enabled'] as bool? ?? false,
      device: json['device'] as String? ?? 'hdmi',
      volume: json['volume'] as int? ?? 50,
    );
  }

  AudioSettings copyWith({
    bool? enabled,
    String? device,
    int? volume,
  }) {
    return AudioSettings(
      enabled: enabled ?? this.enabled,
      device: device ?? this.device,
      volume: volume ?? this.volume,
    );
  }
}

class SyncSettings {
  final int checkIntervalMinutes;
  final String localCacheDir;
  final bool downloadOnStart;
  final int timezoneOffset;
  final bool syncSystemTime;

  SyncSettings({
    this.checkIntervalMinutes = 1,
    this.localCacheDir = './media',
    this.downloadOnStart = false,
    this.timezoneOffset = 8,
    this.syncSystemTime = true,
  });

  Map<String, dynamic> toJson() {
    return {
      'check_interval_minutes': checkIntervalMinutes,
      'local_cache_dir': localCacheDir,
      'download_on_start': downloadOnStart,
      'timezone_offset': timezoneOffset,
      'sync_system_time': syncSystemTime,
    };
  }

  factory SyncSettings.fromJson(Map<String, dynamic> json) {
    return SyncSettings(
      checkIntervalMinutes: json['check_interval_minutes'] as int? ?? 1,
      localCacheDir: json['local_cache_dir'] as String? ?? './media',
      downloadOnStart: json['download_on_start'] as bool? ?? false,
      timezoneOffset: json['timezone_offset'] as int? ?? 8,
      syncSystemTime: json['sync_system_time'] as bool? ?? true,
    );
  }

  SyncSettings copyWith({
    int? checkIntervalMinutes,
    String? localCacheDir,
    bool? downloadOnStart,
    int? timezoneOffset,
    bool? syncSystemTime,
  }) {
    return SyncSettings(
      checkIntervalMinutes: checkIntervalMinutes ?? this.checkIntervalMinutes,
      localCacheDir: localCacheDir ?? this.localCacheDir,
      downloadOnStart: downloadOnStart ?? this.downloadOnStart,
      timezoneOffset: timezoneOffset ?? this.timezoneOffset,
      syncSystemTime: syncSystemTime ?? this.syncSystemTime,
    );
  }
}

class SystemSettings {
  final bool weeklyAutoRestart;
  final String weeklyRestartDay;
  final bool logToRam;
  final int ramLogSizeMb;
  final bool enableHealthMonitoring;
  final int healthCheckIntervalHours;

  SystemSettings({
    this.weeklyAutoRestart = true,
    this.weeklyRestartDay = 'Sun',
    this.logToRam = true,
    this.ramLogSizeMb = 50,
    this.enableHealthMonitoring = true,
    this.healthCheckIntervalHours = 6,
  });

  Map<String, dynamic> toJson() {
    return {
      'weekly_auto_restart': weeklyAutoRestart,
      'weekly_restart_day': weeklyRestartDay,
      'log_to_ram': logToRam,
      'ram_log_size_mb': ramLogSizeMb,
      'enable_health_monitoring': enableHealthMonitoring,
      'health_check_interval_hours': healthCheckIntervalHours,
    };
  }

  factory SystemSettings.fromJson(Map<String, dynamic> json) {
    return SystemSettings(
      weeklyAutoRestart: json['weekly_auto_restart'] as bool? ?? true,
      weeklyRestartDay: json['weekly_restart_day'] as String? ?? 'Sun',
      logToRam: json['log_to_ram'] as bool? ?? true,
      ramLogSizeMb: json['ram_log_size_mb'] as int? ?? 50,
      enableHealthMonitoring: json['enable_health_monitoring'] as bool? ?? true,
      healthCheckIntervalHours: json['health_check_interval_hours'] as int? ?? 6,
    );
  }

  SystemSettings copyWith({
    bool? weeklyAutoRestart,
    String? weeklyRestartDay,
    bool? logToRam,
    int? ramLogSizeMb,
    bool? enableHealthMonitoring,
    int? healthCheckIntervalHours,
  }) {
    return SystemSettings(
      weeklyAutoRestart: weeklyAutoRestart ?? this.weeklyAutoRestart,
      weeklyRestartDay: weeklyRestartDay ?? this.weeklyRestartDay,
      logToRam: logToRam ?? this.logToRam,
      ramLogSizeMb: ramLogSizeMb ?? this.ramLogSizeMb,
      enableHealthMonitoring: enableHealthMonitoring ?? this.enableHealthMonitoring,
      healthCheckIntervalHours: healthCheckIntervalHours ?? this.healthCheckIntervalHours,
    );
  }
}
