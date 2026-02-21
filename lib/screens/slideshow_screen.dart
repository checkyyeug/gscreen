import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/slideshow_provider.dart';
import '../widgets/slideshow_widget.dart';
import '../widgets/status_bar_widget.dart';
import 'settings_screen.dart';

/// Main slideshow screen
class SlideshowScreen extends StatefulWidget {
  const SlideshowScreen({super.key});

  @override
  State<SlideshowScreen> createState() => _SlideshowScreenState();
}

class _SlideshowScreenState extends State<SlideshowScreen> {
  @override
  void initState() {
    super.initState();
    // Set fullscreen on mobile/web
    _setFullscreen();
    // Initialize and sync
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initAndSync();
    });
  }

  void _setFullscreen() {
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  }

  Future<void> _initAndSync() async {
    final provider = context.read<SlideshowProvider>();
    await provider.init();
    if (mounted) {
      await provider.syncMedia();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Consumer<SlideshowProvider>(
        builder: (context, provider, child) {
          return Stack(
            fit: StackFit.expand,
            children: [
              // Slideshow content
              SlideshowWidget(
                currentItem: provider.currentItem,
                settings: provider.settings,
                onTap: () => _handleTap(provider),
              ),

              // Status bar at bottom
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                child: StatusBarWidget(
                  currentItem: provider.currentItem,
                  currentIndex: provider.currentIndex,
                  totalItems: provider.totalItems,
                  settings: provider.settings,
                  countdownSeconds: provider.countdownSeconds,
                  isSyncing: provider.isSyncing,
                  lastSyncTime: provider.lastSyncTime,
                  show: provider.state != SlideshowState.sleeping,
                ),
              ),

              // Loading overlay
              if (provider.state == SlideshowState.loading || provider.isSyncing)
                Container(
                  color: Colors.black54,
                  child: const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        CircularProgressIndicator(color: Colors.white),
                        SizedBox(height: 16),
                        Text(
                          'Loading...',
                          style: TextStyle(color: Colors.white),
                        ),
                      ],
                    ),
                  ),
                ),

              // Error overlay
              if (provider.state == SlideshowState.error)
                _buildErrorOverlay(provider),

              // No media overlay
              if (provider.state == SlideshowState.noMedia)
                _buildNoMediaOverlay(provider),

              // Sleeping overlay
              if (provider.state == SlideshowState.sleeping)
                _buildSleepingOverlay(provider),

              // Countdown overlay
              if (provider.countdownSeconds > 0)
                _buildCountdownOverlay(provider),
            ],
          );
        },
      ),
    );
  }

  void _handleTap(SlideshowProvider provider) {
    // Toggle pause/play on tap
    if (provider.state == SlideshowState.playing) {
      provider.pauseSlideshow();
    } else if (provider.state == SlideshowState.paused) {
      provider.resumeSlideshow();
    } else if (provider.state == SlideshowState.idle) {
      provider.startSlideshow();
    }
  }

  Widget _buildErrorOverlay(SlideshowProvider provider) {
    return Container(
      color: Colors.black87,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(
                Icons.error_outline,
                color: Colors.red,
                size: 64,
              ),
              const SizedBox(height: 16),
              const Text(
                'Error',
                style: TextStyle(
                  color: Colors.red,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                provider.errorMessage ?? 'Unknown error',
                style: const TextStyle(color: Colors.white70),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  ElevatedButton.icon(
                    onPressed: () {
                      provider.stopSlideshow();
                      provider.syncMedia();
                    },
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retry'),
                  ),
                  const SizedBox(width: 16),
                  OutlinedButton.icon(
                    onPressed: () => _openSettings(),
                    icon: const Icon(Icons.settings),
                    label: const Text('Settings'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNoMediaOverlay(SlideshowProvider provider) {
    return Container(
      color: Colors.black87,
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.photo_library_outlined,
              color: Colors.white54,
              size: 80,
            ),
            const SizedBox(height: 16),
            const Text(
              'No Media Available',
              style: TextStyle(
                color: Colors.white,
                fontSize: 24,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Add files to your Google Drive folder',
              style: TextStyle(color: Colors.white54),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                ElevatedButton.icon(
                  onPressed: () => provider.syncMedia(),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Sync Now'),
                ),
                const SizedBox(width: 16),
                OutlinedButton.icon(
                  onPressed: () => _openSettings(),
                  icon: const Icon(Icons.settings),
                  label: const Text('Settings'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSleepingOverlay(SlideshowProvider provider) {
    final remaining = provider.settings.schedule.remainingSeconds;

    return Container(
      color: Colors.black,
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.bedtime,
              color: Colors.white54,
              size: 64,
            ),
            const SizedBox(height: 16),
            const Text(
              'Outside Schedule',
              style: TextStyle(
                color: Colors.white,
                fontSize: 24,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Next start in ${_formatDuration(Duration(seconds: remaining))}',
              style: const TextStyle(color: Colors.white54),
            ),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: () {
                provider.settings = provider.settings.copyWith(
                  schedule: provider.settings.schedule.copyWith(enabled: false),
                );
              },
              icon: const Icon(Icons.play_arrow),
              label: const Text('Play Anyway'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCountdownOverlay(SlideshowProvider provider) {
    return Container(
      color: Colors.black54,
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              '${provider.countdownSeconds}',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 120,
                fontWeight: FontWeight.bold,
              ),
            ),
            const Text(
              'Starting slideshow...',
              style: TextStyle(
                color: Colors.white70,
                fontSize: 24,
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatDuration(Duration duration) {
    final hours = duration.inHours;
    final minutes = duration.inMinutes.remainder(60);
    final seconds = duration.inSeconds.remainder(60);

    if (hours > 0) {
      return '${hours}h ${minutes}m';
    } else if (minutes > 0) {
      return '${minutes}m ${seconds}s';
    } else {
      return '${seconds}s';
    }
  }

  void _openSettings() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => const SettingsScreen(),
      ),
    );
  }
}
