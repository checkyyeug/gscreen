# SD 卡保护快速入门

## 1分钟快速设置

```bash
# 1. 运行安装脚本（需要 root）
sudo bash install_sd_protection.sh

# 2. 重启系统
sudo reboot

# 3. 检查服务状态
systemctl status gscreen
```

## 做了什么？

安装脚本会自动：
- ✅ 创建 RAM 磁盘（tmpfs）用于日志和缓存
- ✅ 配置 journald（系统日志）使用内存存储
- ✅ 禁用 rsyslog（减少冗余写入）
- ✅ 设置自动健康检查（每6小时）
- ✅ 配置每周自动重启
- ✅ 优化 sync 频率（最少5分钟间隔）

## 验证安装

```bash
# 检查 RAM 磁盘
ls -la /dev/shm/gscreen_*

# 查看日志（在内存中）
journalctl -u gscreen -f
tail -f /dev/shm/gscreen_logs/sd_health.log

# 检查健康状态
./check_sd_health.sh

# 查看写入统计
iostat -d 1 | grep mmcblk
```

## 文件位置

| 内容 | 位置 | 存储 |
|------|------|------|
| 程序日志 | `/dev/shm/gscreen_logs/` | RAM |
| 图片缓存 | `/dev/shm/gscreen_cache/` | RAM |
| 系统日志 | `journalctl` | RAM |
| 程序文件 | `/home/rpi4/gscreen/` | SD 卡（只读） |
| 设置文件 | `settings.json` | SD 卡（极少写入） |

## 日常维护

```bash
# 查看当前状态
systemctl status gscreen

# 重启服务
sudo systemctl restart gscreen

# 手动健康检查
./check_sd_health.sh

# 清理缓存（如果需要）
rm -rf /dev/shm/gscreen_cache/*
```

## 故障排查

### 服务无法启动
```bash
# 查看详细错误
journalctl -u gscreen -n 50

# 检查日志目录权限
ls -la /dev/shm/gscreen_*
```

### 日志丢失（重启后）
这是正常的！日志存储在 RAM 中，重启会清空。
如需持久化日志，修改 `gscreen-protected.service` 注释掉 tmpfs 相关行。

### 内存不足
如果系统内存不足：
1. 减少缓存大小：`settings.json` 中减小 `max_cache_size_mb`
2. 减少日志保留：`gscreen-protected.service` 中减小 `size=50m`
3. 添加更多 RAM 或使用 USB 存储

## 预期效果

| 指标 | 优化前 | 优化后 | 改进 |
|------|--------|--------|------|
| 每日 SD 卡写入 | ~500MB | ~10MB | 98%↓ |
| 日志文件数量 | 无限增长 | 轮转 3 个 | 可控 |
| 服务重启后数据 | 累积 | 清空 | 干净 |
| 预期 SD 卡寿命 | 2-3 年 | 5-10 年 | 3x↑ |

## 高级选项

### 使用 USB 存储替代 RAM 缓存
如果图片很多，RAM 不够用：

```bash
# 挂载 USB 存储
sudo mkdir -p /mnt/usb_cache
sudo mount /dev/sda1 /mnt/usb_cache

# 修改 settings.json
# "local_cache_dir": "/mnt/usb_cache"
```

### 完全只读模式（实验性）
```bash
# 切换系统为只读（谨慎使用）
sudo ./readonly_mode.sh
```

### 监控通知
在 `check_sd_health.sh` 中添加邮件/微信通知：

```bash
# 当磨损程度 > 80% 时发送通知
WEAR=$(cat /sys/bus/mmc/devices/*/life_time 2>/dev/null)
if [ $((0x$WEAR * 10)) -gt 80 ]; then
    curl -X POST "https://your-notification-api.com/alert" \
         -d "message=SD Card wear level critical: ${WEAR}%"
fi
```

## 硬件建议

为了最长寿命，建议：

1. **使用工业级 SD 卡**
   - SanDisk Industrial (MLC)
   - Samsung Pro Endurance
   - 容量 ≥ 32GB（更大 = 更长寿命）

2. **良好散热**
   - 避免高温环境
   - 必要时添加散热片

3. **稳定电源**
   - 使用优质电源适配器
   - 考虑 UPS 防止断电损坏

4. **备用方案**
   - 准备备用 SD 卡
   - 定期备份系统镜像

## 一键检查命令

```bash
# 完整健康检查
echo "=== gScreen SD Card Health ===" && \
echo "Date: $(date)" && \
echo "Disk usage:" && df -h / && \
echo "Wear level:" && cat /sys/bus/mmc/devices/*/life_time 2>/dev/null && \
echo "Service status:" && systemctl is-active gscreen && \
echo "Memory usage:" && free -h && \
echo "Cache size:" && du -sh /dev/shm/gscreen_cache 2>/dev/null
```

## 获取更多帮助

- 完整文档：`SD_CARD_PROTECTION.md`
- 代码模块：`sd_card_protection.py`
- 服务配置：`gscreen-protected.service`
- 安装脚本：`install_sd_protection.sh`
