# 功能更新摘要

## 新功能：Settings.json 系统配置

已将以下功能移至 `settings.json` 中配置，默认值安全且合理：

### 1. 每周自动重启（默认：启用）

```json
"system": {
    "weekly_auto_restart": true,
    "weekly_restart_day": 0,
    "weekly_restart_time": "03:00"
}
```

- 每周日 03:00 自动重启系统
- 清理内存，刷新系统状态
- 可配置星期几和具体时间

### 2. 日志写入控制（默认：禁用 RAM 日志）

```json
"system": {
    "log_to_ram": false,
    "ram_log_size_mb": 50
}
```

- `false`：日志输出到 stdout（由 systemd journald 管理）
- `true`：日志写入 RAM (/dev/shm/)，重启后丢失
- 默认禁用 RAM 日志，便于排查问题

## 代码修改

### 修改的文件
1. **main.py** - 从 settings.json 读取日志配置
2. **slideshow.py** - 添加每周重启检查逻辑
3. **gdrive_sync.py** - 简化日志配置
4. **settings.json** - 添加 system 配置段
5. **settings.json.example** - 更新示例配置
6. **install_sd_protection.sh** - 更新安装脚本

## 默认值说明

| 设置 | 默认值 | 说明 |
|------|--------|------|
| weekly_auto_restart | true | 启用每周自动重启 |
| weekly_restart_day | 0 | 周日 (0=周日, 1=周一...) |
| weekly_restart_time | "03:00" | 凌晨 3 点 |
| log_to_ram | false | 不写入 RAM（stdout 输出）|
| ram_log_size_mb | 50 | RAM 日志总大小限制 |

## 如何启用 SD 卡保护模式

编辑 `settings.json`：

```json
"system": {
    "weekly_auto_restart": true,
    "log_to_ram": true,
    "ram_log_size_mb": 50
}
```

重启服务：
```bash
sudo systemctl restart gscreen
```

## 查看日志

### 方式 1：journald（默认，推荐）
```bash
journalctl -u gscreen -f
```

### 方式 2：RAM 日志（启用 log_to_ram 后）
```bash
tail -f /dev/shm/gscreen_logs/gscreen.log
```

## 文件更新列表

- ✓ main.py - 动态日志配置
- ✓ slideshow.py - 自动重启逻辑
- ✓ gdrive_sync.py - 日志简化
- ✓ settings.json - 新配置结构
- ✓ settings.json.example - 更新示例
- ✓ install_sd_protection.sh - 自动配置
- ✓ SETTINGS_GUIDE.md - 配置说明
- ✓ CONFIG_MIGRATION.md - 迁移指南
