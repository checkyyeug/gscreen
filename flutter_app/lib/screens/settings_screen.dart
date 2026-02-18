import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/settings_service.dart';
import '../services/api_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _backendUrlController;
  late TextEditingController _googleDriveUrlController;
  bool _isConnected = false;
  bool _isChecking = false;

  @override
  void initState() {
    super.initState();
    final settings = context.read<SettingsService>();
    _backendUrlController = TextEditingController(text: settings.backendUrl);
    _googleDriveUrlController = TextEditingController(text: settings.googleDriveUrl);
    _checkConnection();
  }

  @override
  void dispose() {
    _backendUrlController.dispose();
    _googleDriveUrlController.dispose();
    super.dispose();
  }

  Future<void> _checkConnection() async {
    setState(() => _isChecking = true);
    final apiService = ApiService()..setBaseUrl(_backendUrlController.text);
    final connected = await apiService.checkConnection();
    setState(() {
      _isConnected = connected;
      _isChecking = false;
    });
  }

  Future<void> _saveSettings() async {
    if (!_formKey.currentState!.validate()) return;

    final settings = context.read<SettingsService>();
    settings.setBackendUrl(_backendUrlController.text);

    // Update remote settings
    final newRemoteSettings = Map<String, dynamic>.from(settings.remoteSettings);
    newRemoteSettings['google_drive_url'] = _googleDriveUrlController.text;

    try {
      await settings.updateRemoteSettings(newRemoteSettings);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Settings saved')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<SettingsService>(
      builder: (context, settings, child) {
        return Scaffold(
          appBar: AppBar(
            title: const Text('Settings'),
            actions: [
              IconButton(
                icon: const Icon(Icons.save),
                onPressed: _saveSettings,
              ),
            ],
          ),
          body: Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Connection Status
                _buildSectionHeader('Connection'),
                Card(
                  child: ListTile(
                    leading: Icon(
                      _isConnected ? Icons.check_circle : Icons.error,
                      color: _isConnected ? Colors.green : Colors.red,
                    ),
                    title: Text(_isConnected ? 'Connected' : 'Disconnected'),
                    subtitle: Text(_isChecking ? 'Checking...' : settings.backendUrl),
                    trailing: _isChecking
                        ? const SizedBox(
                            width: 24,
                            height: 24,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : IconButton(
                            icon: const Icon(Icons.refresh),
                            onPressed: _checkConnection,
                          ),
                  ),
                ),
                const SizedBox(height: 16),

                // Backend URL
                TextFormField(
                  controller: _backendUrlController,
                  decoration: const InputDecoration(
                    labelText: 'Backend URL',
                    hintText: 'http://localhost:8080',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: (_) => _checkConnection(),
                ),
                const SizedBox(height: 24),

                // Google Drive Settings
                _buildSectionHeader('Google Drive'),
                TextFormField(
                  controller: _googleDriveUrlController,
                  decoration: const InputDecoration(
                    labelText: 'Google Drive URL',
                    hintText: 'https://drive.google.com/drive/folders/...',
                    border: OutlineInputBorder(),
                  ),
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please enter a URL';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 24),

                // Display Settings
                _buildSectionHeader('Display'),
                ListTile(
                  title: const Text('Scale Mode'),
                  subtitle: Text(settings.scaleMode),
                  trailing: DropdownButton<String>(
                    value: settings.scaleMode,
                    items: const [
                      DropdownMenuItem(value: 'fit', child: Text('Fit')),
                      DropdownMenuItem(value: 'fill', child: Text('Fill')),
                      DropdownMenuItem(value: 'stretch', child: Text('Stretch')),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        // Update setting
                      }
                    },
                  ),
                ),
                ListTile(
                  title: const Text('Hardware Acceleration'),
                  subtitle: Text(settings.hwAccel),
                  trailing: DropdownButton<String>(
                    value: settings.hwAccel,
                    items: const [
                      DropdownMenuItem(value: 'auto', child: Text('Auto')),
                      DropdownMenuItem(value: 'v4l2m2m', child: Text('V4L2 M2M')),
                      DropdownMenuItem(value: 'drm', child: Text('DRM')),
                      DropdownMenuItem(value: 'none', child: Text('None')),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        // Update setting
                      }
                    },
                  ),
                ),
                const SizedBox(height: 24),

                // Audio Settings
                _buildSectionHeader('Audio'),
                SwitchListTile(
                  title: const Text('Enable Audio'),
                  subtitle: const Text('Play audio for videos'),
                  value: settings.audioEnabled,
                  onChanged: (value) {
                    // Update setting
                  },
                ),
                ListTile(
                  title: const Text('Audio Device'),
                  subtitle: Text(settings.audioDevice.toUpperCase()),
                  trailing: DropdownButton<String>(
                    value: settings.audioDevice,
                    items: const [
                      DropdownMenuItem(value: 'hdmi', child: Text('HDMI')),
                      DropdownMenuItem(value: 'local', child: Text('Headphone')),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        // Update setting
                      }
                    },
                  ),
                ),
                ListTile(
                  title: const Text('Volume'),
                  subtitle: Text('${settings.volume.toInt()}%'),
                  trailing: SizedBox(
                    width: 150,
                    child: Slider(
                      value: settings.volume,
                      min: 0,
                      max: 100,
                      onChanged: (value) {
                        settings.setVolume(value);
                      },
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                // Schedule Settings
                _buildSectionHeader('Schedule'),
                SwitchListTile(
                  title: const Text('Enable Schedule'),
                  subtitle: const Text('Auto on/off at scheduled times'),
                  value: settings.scheduleEnabled,
                  onChanged: (value) {
                    // Update setting
                  },
                ),
                if (settings.scheduleEnabled) ...[
                  ListTile(
                    title: const Text('Start Time'),
                    subtitle: Text(settings.scheduleStart),
                    trailing: const Icon(Icons.access_time),
                    onTap: () async {
                      final time = await showTimePicker(
                        context: context,
                        initialTime: _parseTime(settings.scheduleStart),
                      );
                      if (time != null) {
                        // Update setting
                      }
                    },
                  ),
                  ListTile(
                    title: const Text('Stop Time'),
                    subtitle: Text(settings.scheduleStop),
                    trailing: const Icon(Icons.access_time),
                    onTap: () async {
                      final time = await showTimePicker(
                        context: context,
                        initialTime: _parseTime(settings.scheduleStop),
                      );
                      if (time != null) {
                        // Update setting
                      }
                    },
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: Theme.of(context).colorScheme.primary,
            ),
      ),
    );
  }

  TimeOfDay _parseTime(String time) {
    final parts = time.split(':');
    return TimeOfDay(hour: int.parse(parts[0]), minute: int.parse(parts[1]));
  }
}
