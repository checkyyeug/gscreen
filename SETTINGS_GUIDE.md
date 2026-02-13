# gScreen 设置指南

## 配置文件说明

`settings.json` 包含所有可配置选项。以下按功能分组说明。

---

## System 系统设置（新增）

控制 SD 卡保护和系统维护行为。

```json
"system": {
    "weekly_auto_restart": true,
    "weekly_restart_day": 0,
    
    "log_to_ram": false,
    "ram_log_size_mb": 50,
    "enable_health_monitoring": true,
    "health_check_interval_hours": 6
}
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `weekly_auto_restart` | boolean | `true` | 是否启用每周自动重启 |
| `weekly_restart_day` | int | `0` | 重启日期 (0=周日, 1=周一, ..., 6=周六) |
| `weekly_restart_time` | string | `"03:00"` | 重启时间 (24小时制) |
| `log_to_ram` | boolean | `false` | 是否将日志写入 RAM（保护 SD 卡）|
| `ram_log_size_mb` | int | `50` | RAM 日志总大小限制 |
| `enable_health_monitoring` | boolean | `true` | 是否启用健康监控 |
| `health_check_interval_hours` | int | `6` | 健康检查间隔（小时）|

### 使用建议

**默认配置（推荐）**：
- 每周日 03:00 自动重启（清理内存、刷新系统）
- 日志输出到 stdout（systemd journald 管理，不写入 SD 卡）
- 不启用 RAM 日志（如需查看日志使用 `journalctl`）

**启用 RAM 日志**（最大化 SD 卡保护）：
```json
"system": {
    "log_to_ram": true,
    "ram_log_size_mb": 50
}
```
注意：重启后 RAM 日志会丢失！

**禁用自动重启**：
```json
"system": {
    "weekly_auto_restart": false
}
```

---

## Display 显示设置

控制屏幕显示行为。

```json
"display": {
    "hdmi_port": 1,
    "fullscreen": true,
    "borderless": true,
    "background_color": [0, 0, 0],
    "hide_mouse": true,
    "show_statusbar": true,
    "rotation_mode": "software",
    "rotation": 90,
    "statusbar_layout": {...}
}
```

### 关键参数

| 参数 | 说明 |
|------|------|
| `rotation` | 屏幕旋转角度 (0, 90, 180, 270) |
| `rotation_mode` | `"software"` 或 `"hardware"` |
| `statusbar_layout.opacity` | 状态栏透明度 (0.0-1.0) |

---

## Slideshow 幻灯片设置

```json
"slideshow": {
    "interval_seconds": 5,
    "scale_mode": "fit"
}
```

| 参数 | 说明 |
|------|------|
| `interval_seconds` | 图片切换间隔（秒）|
| `scale_mode` | `"fit"` (适应屏幕), `"fill"` (填充), `"stretch"` (拉伸) |

---

## Schedule 定时设置

控制显示屏的开关时间。

```json
"schedule": {
    "enabled": true,
    "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "start": "07:00",
    "stop": "22:00"
}
```

---

## Sync 同步设置

```json
"sync": {
    "check_interval_minutes": 3,
    "local_cache_dir": "./media",
    "download_on_start": false
}
```

### SD 卡保护建议

**高保护模式**（最少写入）：
```json
"sync": {
    "check_interval_minutes": 60,
    "local_cache_dir": "/dev/shm/gscreen_cache",
    "download_on_start": false
}
```

**使用 USB 存储**：
```json
"sync": {
    "local_cache_dir": "/mnt/usb/gscreen_cache"
}
```

---

## 完整配置示例

### 标准模式（默认）
```json
{
    "google_drive_url": "...",
    "display": {...},
    "slideshow": {...},
    "schedule": {...},
    "sync": {...},
    "system": {
        "weekly_auto_restart": true,
        "weekly_restart_day": 0,
        
        "log_to_ram": false
    }
}
```

### SD 卡保护模式（最大化寿命）
```json
{
    "google_drive_url": "...",
    "display": {...},
    "slideshow": {...},
    "schedule": {...},
    "sync": {
        "check_interval_minutes": 60,
        "local_cache_dir": "/dev/shm/gscreen_cache",
        "download_on_start": false
    },
    "system": {
        "weekly_auto_restart": true,
        "weekly_restart_day": 0,
        
        "log_to_ram": true,
        "ram_log_size_mb": 50
    }
}
```

### 无重启模式（调试/开发）
```json
{
    ...
    "system": {
        "weekly_auto_restart": false,
        "log_to_ram": true
    }
}
```

---

## 配置验证

修改 settings.json 后，运行以下命令验证格式：

```bash
cd /home/rpi4/gscreen
python3 -c "import json; json.load(open('settings.json')); print('✓ 格式正确')"
```

---

## 常见问题

### Q: 如何查看日志？

**方式 1 - 使用 journald（默认）**：
```bash
journalctl -u gscreen -f
```

**方式 2 - RAM 日志（启用 `log_to_ram: true` 后）**：
```bash
tail -f /dev/shm/gscreen_logs/gscreen.log
```

### Q: 自动重启会丢失什么数据？

- 未保存的日志（如果 log_to_ram=true）
- RAM 中的临时文件
- 系统缓存

**不会丢失**：
- Google Drive 上的文件
- 已下载到 SD 卡/USB 的图片
- 设置文件

### Q: 如何手动触发重启？

```bash
sudo systemctl restart gscreen
```

或完全重启系统：
```bash
sudo reboot
```
