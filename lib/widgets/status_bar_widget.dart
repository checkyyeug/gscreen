import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/media_item.dart';
import '../models/app_settings.dart';

/// Status bar widget showing media info and system info
class StatusBarWidget extends StatelessWidget {
  final MediaItem? currentItem;
  final int currentIndex;
  final int totalItems;
  final AppSettings settings;
  final int countdownSeconds;
  final bool isSyncing;
  final DateTime? lastSyncTime;
  final bool show;

  const StatusBarWidget({
    super.key,
    this.currentItem,
    this.currentIndex = 0,
    this.totalItems = 0,
    required this.settings,
    this.countdownSeconds = 0,
    this.isSyncing = false,
    this.lastSyncTime,
    this.show = true,
  });

  @override
  Widget build(BuildContext context) {
    if (!show || !settings.display.showStatusbar) {
      return const SizedBox.shrink();
    }

    final isLandscape = settings.display.rotation == 0 ||
        settings.display.rotation == 180;
    final layout = isLandscape
        ? settings.display.statusbarLayout.landscape
        : settings.display.statusbarLayout.portrait;

    return Opacity(
      opacity: settings.display.statusbarLayout.opacity,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.black54,
        ),
        child: SafeArea(
          top: layout.fileInfoPosition == 'top',
          bottom: layout.fileInfoPosition == 'bottom',
          child: Row(
            children: [
              // File Info (left)
              Expanded(
                flex: 2,
                child: _buildFileInfo(),
              ),
              // Progress (center)
              Expanded(
                flex: 1,
                child: _buildProgress(),
              ),
              // System Info (right)
              Expanded(
                flex: 2,
                child: _buildSystemInfo(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFileInfo() {
    if (currentItem == null) {
      return const Text(
        'No file',
        style: TextStyle(color: Colors.white70, fontSize: 12),
      );
    }

    final item = currentItem!;
    final dateFormat = DateFormat('yyyy-MM-dd HH:mm');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          item.name,
          style: const TextStyle(color: Colors.white, fontSize: 14),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: 2),
        Row(
          children: [
            if (item.modifiedTime != null)
              Text(
                dateFormat.format(item.modifiedTime!),
                style: const TextStyle(color: Colors.white70, fontSize: 10),
              ),
            const SizedBox(width: 8),
            if (item.fileSize != null)
              Text(
                _formatFileSize(item.fileSize!),
                style: const TextStyle(color: Colors.white70, fontSize: 10),
              ),
          ],
        ),
      ],
    );
  }

  Widget _buildProgress() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (countdownSeconds > 0) ...[
          Text(
            'Starting in $countdownSeconds s',
            style: const TextStyle(
              color: Colors.orange,
              fontSize: 14,
              fontWeight: FontWeight.bold,
            ),
          ),
        ] else ...[
          Text(
            '${currentIndex + 1} / $totalItems',
            style: const TextStyle(color: Colors.white, fontSize: 14),
            textAlign: TextAlign.center,
          ),
        ],
        if (isSyncing)
          const SizedBox(
            width: 12,
            height: 12,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: Colors.white,
            ),
          ),
      ],
    );
  }

  Widget _buildSystemInfo() {
    final now = DateTime.now();
    final timeFormat = DateFormat('HH:mm:ss');
    final dateFormat = DateFormat('yyyy-MM-dd');

    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      mainAxisSize: MainAxisSize.min,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            Text(
              timeFormat.format(now),
              style: const TextStyle(color: Colors.white, fontSize: 14),
            ),
            const SizedBox(width: 8),
            Text(
              dateFormat.format(now),
              style: const TextStyle(color: Colors.white70, fontSize: 10),
            ),
          ],
        ),
        if (lastSyncTime != null) ...[
          const SizedBox(height: 2),
          Text(
            'Sync: ${DateFormat('HH:mm').format(lastSyncTime!)}',
            style: const TextStyle(color: Colors.white70, fontSize: 10),
          ),
        ],
        if (currentItem != null) ...[
          const SizedBox(height: 2),
          Text(
            currentItem!.isVideo ? 'VIDEO' : 'IMAGE',
            style: TextStyle(
              color: currentItem!.isVideo ? Colors.red : Colors.green,
              fontSize: 10,
            ),
          ),
        ],
      ],
    );
  }

  String _formatFileSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) {
      return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }
}
