/// Media item model representing a file from Google Drive
class MediaItem {
  final String id;
  final String name;
  final String? downloadUrl;
  final String? webContentLink;
  final DateTime? modifiedTime;
  final int? fileSize;
  final String mimeType;
  final String? thumbnailLink;
  final String localPath;
  final bool isVideo;
  final bool isDownloaded;

  MediaItem({
    required this.id,
    required this.name,
    this.downloadUrl,
    this.webContentLink,
    this.modifiedTime,
    this.fileSize,
    required this.mimeType,
    this.thumbnailLink,
    required this.localPath,
    required this.isVideo,
    this.isDownloaded = false,
  });

  String get extension {
    final dotIndex = name.lastIndexOf('.');
    return dotIndex != -1 ? name.substring(dotIndex).toLowerCase() : '';
  }

  bool get isImage {
    final imgExts = [
      '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
      '.tiff', '.tif', '.tga', '.pbm', '.pgm', '.ppm',
      '.pnm', '.ico', '.pcx', '.dib', '.xbm'
    ];
    return imgExts.contains(extension);
  }

  bool get isSupported {
    final supportedExts = [
      '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
      '.tiff', '.tif', '.tga', '.pbm', '.pgm', '.ppm',
      '.pnm', '.ico', '.pcx', '.dib', '.xbm',
      '.mp4', '.avi', '.mov', '.mkv', '.webm'
    ];
    return supportedExts.contains(extension);
  }

  MediaItem copyWith({
    String? id,
    String? name,
    String? downloadUrl,
    String? webContentLink,
    DateTime? modifiedTime,
    int? fileSize,
    String? mimeType,
    String? thumbnailLink,
    String? localPath,
    bool? isVideo,
    bool? isDownloaded,
  }) {
    return MediaItem(
      id: id ?? this.id,
      name: name ?? this.name,
      downloadUrl: downloadUrl ?? this.downloadUrl,
      webContentLink: webContentLink ?? this.webContentLink,
      modifiedTime: modifiedTime ?? this.modifiedTime,
      fileSize: fileSize ?? this.fileSize,
      mimeType: mimeType ?? this.mimeType,
      thumbnailLink: thumbnailLink ?? this.thumbnailLink,
      localPath: localPath ?? this.localPath,
      isVideo: isVideo ?? this.isVideo,
      isDownloaded: isDownloaded ?? this.isDownloaded,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'downloadUrl': downloadUrl,
      'webContentLink': webContentLink,
      'modifiedTime': modifiedTime?.toIso8601String(),
      'fileSize': fileSize,
      'mimeType': mimeType,
      'thumbnailLink': thumbnailLink,
      'localPath': localPath,
      'isVideo': isVideo,
      'isDownloaded': isDownloaded,
    };
  }

  factory MediaItem.fromJson(Map<String, dynamic> json) {
    return MediaItem(
      id: json['id'] as String,
      name: json['name'] as String,
      downloadUrl: json['downloadUrl'] as String?,
      webContentLink: json['webContentLink'] as String?,
      modifiedTime: json['modifiedTime'] != null
          ? DateTime.parse(json['modifiedTime'] as String)
          : null,
      fileSize: json['fileSize'] as int?,
      mimeType: json['mimeType'] as String,
      thumbnailLink: json['thumbnailLink'] as String?,
      localPath: json['localPath'] as String,
      isVideo: json['isVideo'] as bool,
      isDownloaded: json['isDownloaded'] as bool? ?? false,
    );
  }
}
