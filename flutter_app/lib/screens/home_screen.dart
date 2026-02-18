import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:video_player/video_player.dart';
import 'package:chewie/chewie.dart';
import '../services/api_service.dart';
import '../services/settings_service.dart';
import '../widgets/status_bar.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _apiService = ApiService();
  List<Map<String, dynamic>> _mediaList = [];
  int _currentIndex = 0;
  bool _isPlaying = false;
  bool _isLoading = true;
  String? _error;

  VideoPlayerController? _videoController;
  ChewieController? _chewieController;

  @override
  void initState() {
    super.initState();
    _loadMedia();
  }

  @override
  void dispose() {
    _disposeVideoControllers();
    super.dispose();
  }

  void _disposeVideoControllers() {
    _chewieController?.dispose();
    _videoController?.dispose();
    _chewieController = null;
    _videoController = null;
  }

  Future<void> _loadMedia() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final mediaList = await _apiService.getMediaList();
      setState(() {
        _mediaList = mediaList;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  bool _isVideo(String filename) {
    final ext = filename.toLowerCase();
    return ['.mp4', '.avi', '.mov', '.mkv', '.webm'].any((e) => ext.endsWith(e));
  }

  Future<void> _playVideo(String url) async {
    _disposeVideoControllers();

    _videoController = VideoPlayerController.networkUrl(Uri.parse(url));
    await _videoController!.initialize();

    _chewieController = ChewieController(
      videoPlayerController: _videoController!,
      autoPlay: true,
      looping: false,
      allowFullScreen: true,
      allowMuting: true,
      showControls: false,
    );

    _videoController!.addListener(() {
      if (_videoController!.value.position >= _videoController!.value.duration) {
        _nextMedia();
      }
    });
  }

  void _nextMedia() {
    if (_mediaList.isEmpty) return;
    setState(() {
      _currentIndex = (_currentIndex + 1) % _mediaList.length;
    });
    _loadCurrentMedia();
  }

  void _previousMedia() {
    if (_mediaList.isEmpty) return;
    setState(() {
      _currentIndex = (_currentIndex - 1 + _mediaList.length) % _mediaList.length;
    });
    _loadCurrentMedia();
  }

  Future<void> _loadCurrentMedia() async {
    if (_mediaList.isEmpty) return;

    final media = _mediaList[_currentIndex];
    final filename = media['filename'] ?? media['name'];
    final url = _apiService.getMediaUrl(filename);

    if (_isVideo(filename)) {
      await _playVideo(url);
    } else {
      _disposeVideoControllers();
    }
  }

  Future<void> _toggleSlideshow() async {
    try {
      if (_isPlaying) {
        await _apiService.stopSlideshow();
      } else {
        await _apiService.startSlideshow();
      }
      setState(() {
        _isPlaying = !_isPlaying;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 16),
            Text('Error: $_error'),
            const SizedBox(height: 16),
            ElevatedButton(onPressed: _loadMedia, child: const Text('Retry')),
          ],
        ),
      );
    }

    if (_mediaList.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.photo_library_outlined, size: 48),
            const SizedBox(height: 16),
            const Text('No media files'),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadMedia,
              child: const Text('Refresh'),
            ),
          ],
        ),
      );
    }

    final media = _mediaList[_currentIndex];
    final filename = media['filename'] ?? media['name'] ?? 'Unknown';
    final url = _apiService.getMediaUrl(filename);

    return Stack(
      children: [
        // Media display
        Center(
          child: _isVideo(filename) && _chewieController != null
              ? Chewie(controller: _chewieController!)
              : CachedNetworkImage(
                  imageUrl: url,
                  fit: BoxFit.contain,
                  placeholder: (context, url) => const CircularProgressIndicator(),
                  errorWidget: (context, url, error) => const Icon(Icons.error),
                ),
        ),

        // Status bar
        Positioned(
          bottom: 0,
          left: 0,
          right: 0,
          child: StatusBar(
            currentIndex: _currentIndex + 1,
            total: _mediaList.length,
            filename: filename,
            isPlaying: _isPlaying,
          ),
        ),

        // Navigation controls
        Positioned(
          left: 16,
          right: 16,
          bottom: 80,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              IconButton(
                icon: const Icon(Icons.skip_previous, size: 36),
                onPressed: _previousMedia,
              ),
              FloatingActionButton(
                onPressed: _toggleSlideshow,
                child: Icon(_isPlaying ? Icons.pause : Icons.play_arrow),
              ),
              IconButton(
                icon: const Icon(Icons.skip_next, size: 36),
                onPressed: _nextMedia,
              ),
            ],
          ),
        ),
      ],
    );
  }
}
