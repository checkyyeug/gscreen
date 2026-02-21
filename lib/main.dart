import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/slideshow_provider.dart';
import 'screens/slideshow_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const GScreenApp());
}

/// gScreen - Google Drive Photo Slideshow
/// Cross-platform digital signage application
class GScreenApp extends StatelessWidget {
  const GScreenApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => SlideshowProvider(),
      child: MaterialApp(
        title: 'gScreen',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: Colors.blue,
            brightness: Brightness.dark,
          ),
          useMaterial3: true,
        ),
        home: const SlideshowScreen(),
      ),
    );
  }
}
