# gScreen Flet App

Cross-platform UI for gScreen using [Flet](https://flet.dev/).

## 支持平台

- Android
- Windows
- Linux
- macOS
- iOS
- Web

## 架构

```
┌─────────────────────────────────────────────┐
│         Flet UI Layer (Python)              │
│  (Android / Windows / Linux / iOS / Web)   │
├─────────────────────────────────────────────┤
│         Python Core (Direct Import)         │
│  - Google Drive Sync                        │
│  - Media Processing                         │
│  - Hardware Detection                       │
│  - Slideshow Control                        │
└─────────────────────────────────────────────┘
```

## 安装

```bash
# 安装依赖
cd flet_app
pip install -r requirements.txt
```

## 运行

### 桌面端 (Windows/Linux/macOS)
```bash
python main.py
```

### Android
```bash
# 构建 APK
flet build apk

# 或直接在连接的设备上运行
flet run --android
```

### Web
```bash
flet run --web
```

## 功能

### Slideshow 页面
- 图片/视频显示
- 上一个/下一个控制
- 播放/暂停
- 进度显示

### Sync 页面
- Google Drive 同步
- 同步状态显示
- 同步日志

### Settings 页面
- Google Drive URL 配置
- 显示设置 (缩放模式、硬件加速、旋转)
- 音频设置 (启用、设备、音量)
- 同步间隔

### Hardware 页面
- 硬件检测结果
- 音频系统信息
- 配置建议
- 警告和建议

## 项目结构

```
flet_app/
├── main.py           # 主应用
├── requirements.txt  # Python 依赖
└── README.md         # 文档
```

## 截图

_待添加_

## 构建发布版本

```bash
# Android APK
flet build apk --release

# Windows
flet build windows --release

# Linux
flet build linux --release

# macOS
flet build macos --release

# Web
flet build web --release
```
