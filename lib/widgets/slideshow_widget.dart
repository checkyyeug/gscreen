import 'dart:io';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../models/media_item.dart';
import '../models/app_settings.dart';

/// Widget for displaying slideshow media (images and videos)
class SlideshowWidget extends StatefulWidget {
  final MediaItem? currentItem;
  final AppSettings settings;
  final VoidCallback? onTap;

  const SlideshowWidget({
    super.key,
    this.currentItem,
    required this.settings,
    this.onTap,
  });

  @override
  State<SlideshowWidget> createState() => _SlideshowWidgetState();
}

class _SlideshowWidgetState extends State<SlideshowWidget> {
  VideoPlayerController? _videoController;
  bool _isVideoInitialized = false;
  bool _isVideoPlaying = false;

  @override
  void didUpdateWidget(SlideshowWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.currentItem?.id != widget.currentItem?.id) {
      _handleMediaChange();
    }
  }

  void _handleMediaChange() {
    _disposeVideoController();

    if (widget.currentItem == null) return;

    if (widget.currentItem!.isVideo) {
      _initVideo();
    }
  }

  Future<void> _initVideo() async {
    if (widget.currentItem == null || !widget.currentItem!.isVideo) return;

    final file = File(widget.currentItem!.localPath);

    // Check if file exists locally
    if (!await file.exists()) {
      return;
    }

    _videoController = VideoPlayerController.file(file);

    try {
      await _videoController!.initialize();
      setState(() {
        _isVideoInitialized = true;
      });
      await _videoController!.setLooping(true);
      await _videoController!.play();
      setState(() {
        _isVideoPlaying = true;
      });

      _videoController!.addListener(_videoListener);
    } catch (e) {
      debugPrint('Error initializing video: $e');
    }
  }

  void _videoListener() {
    if (_videoController == null) return;

    final playing = _videoController!.value.isPlaying;
    if (playing != _isVideoPlaying) {
      setState(() {
        _isVideoPlaying = playing;
      });
    }
  }

  void _disposeVideoController() {
    _videoController?.removeListener(_videoListener);
    _videoController?.dispose();
    _videoController = null;
    _isVideoInitialized = false;
    _isVideoPlaying = false;
  }

  @override
  void dispose() {
    _disposeVideoController();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.currentItem == null) {
      return _buildNoMedia();
    }

    // Get rotation angle
    final rotationAngle = widget.settings.display.rotation * math.pi / 180;

    return GestureDetector(
      onTap: widget.onTap,
      child: RotatedBox(
        quarterTurns: widget.settings.display.rotation ~/ 90,
        child: Container(
          color: Color.fromRGBO(
            widget.settings.display.backgroundColor[0],
            widget.settings.display.backgroundColor[1],
            widget.settings.display.backgroundColor[2],
            1,
          ),
          child: widget.currentItem!.isVideo
              ? _buildVideo()
              : _buildImage(),
        ),
      ),
    );
  }

  Widget _buildNoMedia() {
    return Container(
      color: Color.fromRGBO(
        widget.settings.display.backgroundColor[0],
        widget.settings.display.backgroundColor[1],
        widget.settings.display.backgroundColor[2],
        1,
      ),
      child: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.photo_library_outlined,
              size: 80,
              color: Colors.white54,
            ),
            SizedBox(height: 16),
            Text(
              'No Media Available',
              style: TextStyle(
                color: Colors.white70,
                fontSize: 24,
              ),
            ),
            SizedBox(height: 8),
            Text(
              'Add files to your Google Drive folder',
              style: TextStyle(
                color: Colors.white54,
                fontSize: 16,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildImage() {
    final item = widget.currentItem!;
    final file = File(item.localPath);

    if (item.isDownloaded && file.existsSync()) {
      // Load from local file
      return Image.file(
        file,
        fit: _getBoxFit(),
        width: double.infinity,
        height: double.infinity,
        errorBuilder: (context, error, stackTrace) => _buildImageError(),
      );
    }

    // Try to load from network
    if (item.thumbnailLink != null) {
      return CachedNetworkImage(
        imageUrl: item.thumbnailLink!,
        fit: _getBoxFit(),
        width: double.infinity,
        height: double.infinity,
        placeholder: (context, url) => _buildLoading(),
        errorWidget: (context, url, error) => _buildImageError(),
      );
    }

    return _buildImageError();
  }

  Widget _buildVideo() {
    if (!_isVideoInitialized || _videoController == null) {
      return Container(
        color: Colors.black,
        child: const Center(
          child: CircularProgressIndicator(color: Colors.white),
        ),
      );
    }

    return Center(
      child: AspectRatio(
        aspectRatio: _videoController!.value.aspectRatio,
        child: VideoPlayer(_videoController!),
      ),
    );
  }

  Widget _buildLoading() {
    return Container(
      color: Color.fromRGBO(
        widget.settings.display.backgroundColor[0],
        widget.settings.display.backgroundColor[1],
        widget.settings.display.backgroundColor[2],
        1,
      ),
      child: const Center(
        child: CircularProgressIndicator(color: Colors.white),
      ),
    );
  }

  Widget _buildImageError() {
    return Container(
      color: Color.fromRGBO(
        widget.settings.display.backgroundColor[0],
        widget.settings.display.backgroundColor[1],
        widget.settings.display.backgroundColor[2],
        1,
      ),
      child: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.broken_image_outlined,
              size: 64,
              color: Colors.white54,
            ),
            SizedBox(height: 8),
            Text(
              'Failed to load image',
              style: TextStyle(color: Colors.white54),
            ),
          ],
        ),
      ),
    );
  }

  BoxFit _getBoxFit() {
    switch (widget.settings.slideshow.scaleMode) {
      case 'fill':
        return BoxFit.cover;
      case 'stretch':
        return BoxFit.fill;
      case 'fit':
      default:
        return BoxFit.contain;
    }
  }
}
