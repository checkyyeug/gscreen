import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/app_settings.dart';
import '../providers/slideshow_provider.dart';

/// Settings screen for configuring the app
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _urlController;
  late TextEditingController _intervalController;

  @override
  void initState() {
    super.initState();
    final provider = context.read<SlideshowProvider>();
    _urlController = TextEditingController(text: provider.settings.googleDriveUrl);
    _intervalController = TextEditingController(
      text: provider.settings.slideshow.intervalSeconds.toString(),
    );
  }

  @override
  void dispose() {
    _urlController.dispose();
    _intervalController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        backgroundColor: Theme.of(context).colorScheme.inversePrimary,
      ),
      body: Consumer<SlideshowProvider>(
        builder: (context, provider, child) {
          return Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                // Google Drive Section
                _buildSectionTitle('Google Drive'),
                TextFormField(
                  controller: _urlController,
                  decoration: const InputDecoration(
                    labelText: 'Google Drive Folder URL',
                    hintText: 'https://drive.google.com/drive/folders/...',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.link),
                  ),
                  keyboardType: TextInputType.url,
                  validator: (value) {
                    if (value != null && value.isNotEmpty) {
                      if (!value.contains('drive.google.com')) {
                        return 'Please enter a valid Google Drive URL';
                      }
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 8),
                const Text(
                  'Note: The folder must be set to "Anyone with the link can view"',
                  style: TextStyle(color: Colors.grey, fontSize: 12),
                ),

                const SizedBox(height: 24),

                // Slideshow Section
                _buildSectionTitle('Slideshow'),
                TextFormField(
                  controller: _intervalController,
                  decoration: const InputDecoration(
                    labelText: 'Interval (seconds)',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.timer),
                  ),
                  keyboardType: TextInputType.number,
                  validator: (value) {
                    if (value == null || value.isEmpty) {
                      return 'Please enter an interval';
                    }
                    final interval = int.tryParse(value);
                    if (interval == null || interval < 1) {
                      return 'Interval must be at least 1 second';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  value: provider.settings.slideshow.scaleMode,
                  decoration: const InputDecoration(
                    labelText: 'Scale Mode',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.aspect_ratio),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'fit', child: Text('Fit (with borders)')),
                    DropdownMenuItem(value: 'fill', child: Text('Fill (crop to fit)')),
                    DropdownMenuItem(value: 'stretch', child: Text('Stretch')),
                  ],
                  onChanged: (value) {
                    if (value != null) {
                      provider.updateSettings(
                        provider.settings.copyWith(
                          slideshow: provider.settings.slideshow.copyWith(scaleMode: value),
                        ),
                      );
                    }
                  },
                ),

                const SizedBox(height: 24),

                // Schedule Section
                _buildSectionTitle('Schedule'),
                SwitchListTile(
                  title: const Text('Enable Schedule'),
                  subtitle: const Text('Limit playback to specific times'),
                  value: provider.settings.schedule.enabled,
                  onChanged: (value) {
                    provider.updateSettings(
                      provider.settings.copyWith(
                        schedule: provider.settings.schedule.copyWith(enabled: value),
                      ),
                    );
                  },
                ),
                if (provider.settings.schedule.enabled) ...[
                  ListTile(
                    title: const Text('Start Time'),
                    subtitle: Text(provider.settings.schedule.start),
                    trailing: const Icon(Icons.access_time),
                    onTap: () => _selectTime(context, true, provider),
                  ),
                  ListTile(
                    title: const Text('Stop Time'),
                    subtitle: Text(provider.settings.schedule.stop),
                    trailing: const Icon(Icons.access_time),
                    onTap: () => _selectTime(context, false, provider),
                  ),
                  const Text(
                    'Active Days:',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  Wrap(
                    spacing: 8,
                    children: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                        .map((day) => FilterChip(
                              label: Text(day),
                              selected: provider.settings.schedule.days.contains(day),
                              onSelected: (selected) {
                                final days = List<String>.from(provider.settings.schedule.days);
                                if (selected) {
                                  days.add(day);
                                } else {
                                  days.remove(day);
                                }
                                provider.updateSettings(
                                  provider.settings.copyWith(
                                    schedule: provider.settings.schedule.copyWith(days: days),
                                  ),
                                );
                              },
                            ))
                        .toList(),
                  ),
                ],

                const SizedBox(height: 24),

                // Display Section
                _buildSectionTitle('Display'),
                SwitchListTile(
                  title: const Text('Show Status Bar'),
                  value: provider.settings.display.showStatusbar,
                  onChanged: (value) {
                    provider.updateSettings(
                      provider.settings.copyWith(
                        display: provider.settings.display.copyWith(showStatusbar: value),
                      ),
                    );
                  },
                ),
                SwitchListTile(
                  title: const Text('Fullscreen'),
                  value: provider.settings.display.fullscreen,
                  onChanged: (value) {
                    provider.updateSettings(
                      provider.settings.copyWith(
                        display: provider.settings.display.copyWith(fullscreen: value),
                      ),
                    );
                  },
                ),
                DropdownButtonFormField<int>(
                  value: provider.settings.display.rotation,
                  decoration: const InputDecoration(
                    labelText: 'Rotation',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.screen_rotation),
                  ),
                  items: const [
                    DropdownMenuItem(value: 0, child: Text('0° (Normal)')),
                    DropdownMenuItem(value: 90, child: Text('90° (Portrait)')),
                    DropdownMenuItem(value: 180, child: Text('180° (Upside down)')),
                    DropdownMenuItem(value: 270, child: Text('270° (Portrait)')),
                  ],
                  onChanged: (value) {
                    if (value != null) {
                      provider.updateSettings(
                        provider.settings.copyWith(
                          display: provider.settings.display.copyWith(rotation: value),
                        ),
                      );
                    }
                  },
                ),

                const SizedBox(height: 24),

                // Audio Section
                _buildSectionTitle('Audio'),
                SwitchListTile(
                  title: const Text('Enable Audio'),
                  subtitle: const Text('Play audio in videos'),
                  value: provider.settings.audio.enabled,
                  onChanged: (value) {
                    provider.updateSettings(
                      provider.settings.copyWith(
                        audio: provider.settings.audio.copyWith(enabled: value),
                      ),
                    );
                  },
                ),
                if (provider.settings.audio.enabled)
                  DropdownButtonFormField<String>(
                    value: provider.settings.audio.device,
                    decoration: const InputDecoration(
                      labelText: 'Audio Device',
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.volume_up),
                    ),
                    items: const [
                      DropdownMenuItem(value: 'hdmi', child: Text('HDMI')),
                      DropdownMenuItem(value: 'local', child: Text('Headphone Jack')),
                    ],
                    onChanged: (value) {
                      if (value != null) {
                        provider.updateSettings(
                          provider.settings.copyWith(
                            audio: provider.settings.audio.copyWith(device: value),
                          ),
                        );
                      }
                    },
                  ),

                const SizedBox(height: 24),

                // Sync Section
                _buildSectionTitle('Sync'),
                SwitchListTile(
                  title: const Text('Download on Start'),
                  subtitle: const Text('Download all media when app starts'),
                  value: provider.settings.sync.downloadOnStart,
                  onChanged: (value) {
                    provider.updateSettings(
                      provider.settings.copyWith(
                        sync: provider.settings.sync.copyWith(downloadOnStart: value),
                      ),
                    );
                  },
                ),

                const SizedBox(height: 32),

                // Save Button
                FilledButton.icon(
                  onPressed: _saveSettings,
                  icon: const Icon(Icons.save),
                  label: const Text('Save & Restart'),
                ),

                const SizedBox(height: 16),

                // Manual Sync Button
                OutlinedButton.icon(
                  onPressed: () async {
                    await provider.syncMedia();
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Sync completed')),
                      );
                    }
                  },
                  icon: const Icon(Icons.sync),
                  label: const Text('Sync Now'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Future<void> _selectTime(BuildContext context, bool isStart, SlideshowProvider provider) async {
    final currentTime = isStart
        ? provider.settings.schedule.start
        : provider.settings.schedule.stop;

    final parts = currentTime.split(':');
    final initialTime = TimeOfDay(
      hour: int.parse(parts[0]),
      minute: int.parse(parts[1]),
    );

    final selectedTime = await showTimePicker(
      context: context,
      initialTime: initialTime,
    );

    if (selectedTime != null) {
      final timeString =
          '${selectedTime.hour.toString().padLeft(2, '0')}:${selectedTime.minute.toString().padLeft(2, '0')}';

      if (isStart) {
        provider.updateSettings(
          provider.settings.copyWith(
            schedule: provider.settings.schedule.copyWith(start: timeString),
          ),
        );
      } else {
        provider.updateSettings(
          provider.settings.copyWith(
            schedule: provider.settings.schedule.copyWith(stop: timeString),
          ),
        );
      }
    }
  }

  void _saveSettings() {
    if (_formKey.currentState!.validate()) {
      final provider = context.read<SlideshowProvider>();

      provider.updateSettings(
        provider.settings.copyWith(
          googleDriveUrl: _urlController.text,
          slideshow: provider.settings.slideshow.copyWith(
            intervalSeconds: int.parse(_intervalController.text),
          ),
        ),
      );

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Settings saved')),
      );

      // Restart slideshow with new settings
      provider.stopSlideshow();
      provider.syncMedia();
      provider.startSlideshow();

      Navigator.of(context).pop();
    }
  }
}
