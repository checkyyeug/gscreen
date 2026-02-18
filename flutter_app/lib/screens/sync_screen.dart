import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/settings_service.dart';

class SyncScreen extends StatefulWidget {
  const SyncScreen({super.key});

  @override
  State<SyncScreen> createState() => _SyncScreenState();
}

class _SyncScreenState extends State<SyncScreen> {
  final ApiService _apiService = ApiService();
  bool _isSyncing = false;
  Map<String, dynamic>? _syncStatus;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadSyncStatus();
  }

  Future<void> _loadSyncStatus() async {
    try {
      final status = await _apiService.getSyncStatus();
      setState(() {
        _syncStatus = status;
        _error = null;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    }
  }

  Future<void> _startSync() async {
    setState(() {
      _isSyncing = true;
      _error = null;
    });

    try {
      await _apiService.startSync();
      // Poll for status updates
      for (int i = 0; i < 30; i++) {
        await Future.delayed(const Duration(seconds: 1));
        await _loadSyncStatus();
        if (_syncStatus?['status'] == 'completed' || _syncStatus?['status'] == 'error') {
          break;
        }
      }
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    } finally {
      setState(() {
        _isSyncing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sync'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _isSyncing ? null : _loadSyncStatus,
          ),
        ],
      ),
      body: _buildBody(),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _isSyncing ? null : _startSync,
        icon: _isSyncing
            ? const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : const Icon(Icons.sync),
        label: Text(_isSyncing ? 'Syncing...' : 'Sync Now'),
      ),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 16),
            Text('Error: $_error'),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadSyncStatus,
              child: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Sync Status Card
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(
                      _getStatusIcon(),
                      color: _getStatusColor(),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'Sync Status',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                _buildStatusRow('Status', _syncStatus?['status'] ?? 'Unknown'),
                _buildStatusRow('Last Sync', _syncStatus?['last_sync'] ?? 'Never'),
                _buildStatusRow('Files Total', '${_syncStatus?['total_files'] ?? 0}'),
                _buildStatusRow('Files Synced', '${_syncStatus?['synced_files'] ?? 0}'),
                if (_isSyncing || _syncStatus?['status'] == 'syncing') ...[
                  const SizedBox(height: 16),
                  const LinearProgressIndicator(),
                  const SizedBox(height: 8),
                  Text(
                    'Syncing: ${_syncStatus?['current_file'] ?? 'Preparing...'}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),

        // Google Drive Info
        Card(
          child: ListTile(
            leading: const Icon(Icons.cloud),
            title: const Text('Google Drive'),
            subtitle: Consumer<SettingsService>(
              builder: (context, settings, _) {
                final url = settings.googleDriveUrl;
                if (url.startsWith('file:')) {
                  return const Text('URL loaded from external file');
                }
                return Text(
                  url.isEmpty ? 'Not configured' : url,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                );
              },
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              // Navigate to settings
            },
          ),
        ),
        const SizedBox(height: 24),

        // Sync History
        Text(
          'Recent Activity',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        Card(
          child: Column(
            children: [
              _buildActivityItem(Icons.download_done, 'Downloaded image1.jpg', '2 minutes ago'),
              _buildActivityItem(Icons.download_done, 'Downloaded video1.mp4', '5 minutes ago'),
              _buildActivityItem(Icons.check_circle, 'Sync completed', '10 minutes ago'),
              _buildActivityItem(Icons.cloud_sync, 'Sync started', '12 minutes ago'),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildStatusRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodyMedium),
          Text(value, style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _buildActivityItem(IconData icon, String title, String time) {
    return ListTile(
      leading: Icon(icon, size: 20),
      title: Text(title, style: Theme.of(context).textTheme.bodyMedium),
      subtitle: Text(time, style: Theme.of(context).textTheme.bodySmall),
    );
  }

  IconData _getStatusIcon() {
    final status = _syncStatus?['status'];
    switch (status) {
      case 'syncing':
        return Icons.sync;
      case 'completed':
        return Icons.check_circle;
      case 'error':
        return Icons.error;
      default:
        return Icons.cloud_off;
    }
  }

  Color _getStatusColor() {
    final status = _syncStatus?['status'];
    switch (status) {
      case 'syncing':
        return Colors.blue;
      case 'completed':
        return Colors.green;
      case 'error':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }
}
