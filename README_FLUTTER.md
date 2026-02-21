# gScreen Flutter - Cross-Platform Edition

Google Drive Photo Slideshow 跨平台版本，使用 Flutter 构建。

## 支持的平台

| 平台 | 状态 | 说明 |
|------|------|------|
| Android | ✅ 已测试 | APK 构建成功 |
| Windows | ✅ 已测试 | EXE 构建成功 |
| Chrome/Web | ✅ 已测试 | Web 构建成功 |
| Raspberry Pi (Linux ARM) | ⚠️ 需要交叉编译 | 需要在 Linux 主机上编译 |
| iOS | ⚠️ 未测试 | 需要 macOS 和 Xcode |

## 快速开始

### Windows 运行命令

```powershell
# 方式1: 使用 Flutter 运行（带调试、热重载）
cd C:\workspace\gscreen
flutter run -d windows

# 方式2: 直接运行已构建的 EXE
.\build\windows\x64\runner\Release\gscreen_flutter.exe

# 方式3: 运行 Python 后端进行 Google Drive 同步（仅同步）
cd C:\workspace\gscreen
python main.py --sync-only

# 方式4: 运行完整 Python 程序（需要 RPi 或 Linux 桌面）
cd /path/to/gscreen
python main.py
```

### 前置要求

- **Flutter**: 3.x+
- **Python**: 3.8+ (用于后端同步)
- **Python 依赖**: pygame-ce, gdown, requests, tenacity, Pillow

安装 Python 依赖:
```powershell
pip install pygame-ce gdown requests tenacity Pillow
```

## 功能特性

- 从 Google Drive 文件夹同步照片和视频
- 自动幻灯片播放（图片和视频）
- 定时播放计划（可设置播放时间段）
- 状态栏显示文件信息和系统状态
- 多种显示模式（适应/填充/拉伸）
- 屏幕旋转支持（0°/90°/180°/270°）
- 音频播放支持
- 增量同步（只下载新文件）

## 构建指南

### 前置要求

- Flutter SDK 3.x+
- Android SDK（Android 构建）
- Visual Studio（Windows 构建）

### 构建命令

```bash
# 获取依赖
flutter pub get

# Android APK
flutter build apk --debug
# 或 release 版本
flutter build apk --release

# Windows EXE
flutter build windows

# Web (Chrome)
flutter build web

# Linux (需要在 Linux 主机上)
flutter build linux
```

### 交叉编译到 Raspberry Pi

在 Linux 主机上：

```bash
# 添加 ARM 支持
flutter config --enable-linux-desktop

# 编译 Linux 版本
flutter build linux

# 输出目录: build/linux/x64/release/bundle/
```

## 配置说明

### Google Drive 设置

1. 创建一个公开的 Google Drive 文件夹
2. 将文件夹链接设置为"知道链接的人可以查看"
3. 在应用设置中输入文件夹 URL

### 设置选项

在应用内可以配置：

- **Google Drive URL**: Google Drive 文件夹链接
- **播放间隔**: 图片切换时间（秒）
- **显示模式**: 适应/填充/拉伸
- **播放计划**: 设置播放时间段
- **屏幕旋转**: 0°/90°/180°/270°
- **状态栏**: 显示/隐藏状态信息

## 项目结构

```
gscreen/
├── main.py                 # Python 后端入口
├── gdrive_sync.py          # Google Drive 同步模块
├── slideshow.py            # Python 幻灯片显示
├── settings.json           # 配置文件
├── google_drive.url        # Google Drive 文件夹链接
├── lib/                    # Flutter 前端
│   ├── main.dart           # Flutter 入口
│   ├── services/
│   │   ├── python_service.dart   # Flutter 调用 Python
│   │   └── google_drive_service.dart
│   └── ...
└── build/                  # 构建输出
```

## Flutter + Python 混合模式

Flutter 版本采用混合架构：
- **Flutter 前端**: 跨平台 UI（Windows, Android, Web, iOS）
- **Python 后端**: Google Drive 同步（可复用原版逻辑）

### Windows 上如何工作

1. Flutter 应用启动，显示 UI
2. 用户点击"同步"按钮
3. Flutter 调用 `python_service.dart`
4. Python 后端执行 Google Drive 同步
5. 同步完成后，Flutter 显示本地媒体文件

### Python 集成配置

确保以下文件存在：
- `settings.json` - 应用配置
- `google_drive.url` - Google Drive 文件夹链接（填入真实 ID）

```powershell
# 示例 google_drive.url 内容:
https://drive.google.com/drive/folders/1abc123def456...
```

## 与原版 Python 项目的区别

| 特性 | Python 版本 | Flutter 版本 |
|------|-------------|--------------|
| 平台支持 | RPi, Linux | 全平台 |
| 依赖 | SDL2, Pygame | Flutter SDK |
| 视频硬件加速 | V4L2, DRM | 原生视频播放器 |
| 安装方式 | Shell 脚本 | Flutter 构建 |

## 许可证

MIT License
