# 配置迁移指南

## 从旧版本升级

如果你在使用旧版本的 gScreen（没有 `system` 配置段），请按以下步骤升级：

### 自动升级（推荐）

```bash
cd /home/rpi4/gscreen

# 1. 备份当前配置
cp settings.json settings.json.backup.$(date +%Y%m%d)

# 2. 运行安装脚本（会自动添加新配置）
sudo bash install_sd_protection.sh
```

### 手动升级

在 `settings.json` 中添加以下内容：

```json
{
    ... 现有配置 ...
    "sync": {
        ... 现有 sync 配置 ...
    },
    "system": {
        "_comment": "System-level settings for SD card protection and maintenance",
        "weekly_auto_restart": true,
        "weekly_restart_day": 0,
        
        "log_to_ram": false,
        "ram_log_size_mb": 50,
        "enable_health_monitoring": true,
        "health_check_interval_hours": 6
    },
    "supported_formats": [...]
}
```

### 验证升级

```bash
python3 -c "import json; d=json.load(open('settings.json')); \
    print('✓ system 配置:', '存在' if 'system' in d else '缺失')"
```

---

## 默认行为说明

### 日志行为

| `log_to_ram` | 日志位置 | 重启后 | 适用场景 |
|-------------|---------|--------|---------|
| `false` (默认) | stdout → systemd journald | 保留（如果 journald 配置为持久化）| 大多数用户 |
| `true` | RAM (/dev/shm/) | 丢失 | SD 卡保护优先 |

### 自动重启行为

| `weekly_auto_restart` | 行为 |
|----------------------|------|
| `true` (默认) | 每周日 03:00 自动重启系统 |
| `false` | 不自动重启 |

**注意**：即使启用自动重启，每天只会执行一次，防止意外多次重启。

---

## 推荐的配置组合

### 场景 1：展示用途（最少维护）
```json
"system": {
    "weekly_auto_restart": true,
    "log_to_ram": false
}
```

### 场景 2：SD 卡寿命优先
```json
"system": {
    "weekly_auto_restart": true,
    "log_to_ram": true,
    "ram_log_size_mb": 30
}
```

### 场景 3：调试/开发
```json
"system": {
    "weekly_auto_restart": false,
    "log_to_ram": true
}
```

### 场景 4：工业级部署
```json
"system": {
    "weekly_auto_restart": true,
    "weekly_restart_day": 1,
    "weekly_restart_time": "02:00",
    "log_to_ram": false,
    "enable_health_monitoring": true,
    "health_check_interval_hours": 4
}
```
周一 02:00 重启，每 4 小时健康检查。

---

## 故障排查

### 问题：自动重启没有发生

1. 检查配置是否正确加载：
```bash
journalctl -u gscreen | grep "auto-restart"
```

2. 检查 sudo 权限（重启需要 root）：
```bash
sudo grep gscreen /etc/sudoers
```

3. 手动测试重启功能：
```bash
sudo systemctl reboot
```

### 问题：日志没有写入 RAM

1. 检查 `log_to_ram` 是否为 `true`
2. 检查 RAM 目录是否存在：
```bash
ls -la /dev/shm/gscreen_logs/
```
3. 重启服务后检查：
```bash
sudo systemctl restart gscreen
```

---

## 旧配置兼容性

- 如果没有 `system` 配置段，程序会使用默认值
- 默认值设计为安全且合理的设置
- 不会破坏现有功能
