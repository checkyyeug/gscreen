# SD 卡长期运行保护指南

## 为什么需要保护 SD 卡？

SD 卡使用闪存（Flash Memory），有**写入寿命限制**：
- 普通 SD 卡：约 1,000 - 10,000 次写入/擦除周期
- 工业级 SD 卡：约 100,000 次写入/擦除周期
- 每天 100MB 写入，普通卡约 2-5 年寿命

## 当前风险分析

### 🔴 高风险
| 操作 | 频率 | 风险 |
|------|------|------|
| 日志写入 | 每次操作 | 频繁小写入加速磨损 |
| 图片同步 | 每3分钟 | 频繁下载/删除文件 |
| 临时文件 | 视频播放时 | 临时文件写入 |

### 🟡 中风险
| 操作 | 风险 |
|------|------|
| 设置文件读取 | 只读，无风险 |
| 图片显示 | 只读，无风险 |

## 保护方案

### 方案 1：日志写入 RAM（推荐）

```bash
# 1. 创建 RAM 磁盘日志目录
sudo mkdir -p /dev/shm/gscreen_logs

# 2. 修改 run.sh，添加日志重定向
#!/bin/bash
cd /home/rpi4/gscreen
source venv/bin/activate

# 日志写入 RAM 磁盘
mkdir -p /dev/shm/gscreen_logs
python3 main.py "$@" 2>&1 | tee /dev/shm/gscreen_logs/gscreen.log
```

### 方案 2：使用 tmpfs（RAM 磁盘）

```bash
# 编辑 /etc/fstab，添加 tmpfs 挂载
sudo nano /etc/fstab

# 添加以下行：
tmpfs /var/log/gscreen tmpfs defaults,noatime,nosuid,size=50m 0 0
tmpfs /tmp/gscreen_cache tmpfs defaults,noatime,nosuid,size=200m 0 0

# 重启后生效
sudo reboot
```

### 方案 3：减少 sync 频率

修改 `settings.json`：
```json
{
    "sync": {
        "check_interval_minutes": 60,  // 改为60分钟（原来是3分钟）
        "local_cache_dir": "/tmp/gscreen_cache"  // 使用 tmpfs
    }
}
```

### 方案 4：使用工业级 SD 卡

推荐品牌：
- SanDisk Industrial (SLC/MLC)
- Samsung Pro Endurance
- Transcend High Endurance

## 监控脚本

### SD 卡健康检查

```bash
#!/bin/bash
# /home/rpi4/gscreen/check_sd_health.sh

echo "=== SD Card Health Check ==="
echo "Date: $(date)"

# 磁盘空间
echo -e "\n--- Disk Usage ---"
df -h /

# 尝试读取 SD 卡磨损程度
echo -e "\n--- Wear Level (if available) ---"
for dev in /sys/bus/mmc/devices/*; do
    if [ -f "$dev/life_time" ]; then
        wear=$(cat "$dev/life_time")
        echo "Device: $dev, Wear: 0x$wear"
        # 0x01 = 0-10%, 0x0A = 90-100%
    fi
done

# 写入统计（需要 iostat）
if command -v iostat &> /dev/null; then
    echo -e "\n--- IO Stats ---"
    iostat -d 1 1 | grep -E "(Device|mmcblk)"
fi

# 文件系统错误检查
echo -e "\n--- Filesystem Errors ---"
sudo dmesg | grep -i "i/o error\|corrupt\|filesystem" | tail -5

echo -e "\n=== Check Complete ==="
```

添加到 crontab 每天运行：
```bash
crontab -e
# 添加：
0 9 * * * /home/rpi4/gscreen/check_sd_health.sh >> /tmp/sd_health.log 2>&1
```

## 优化后的系统配置

### 1. Systemd 服务（写入最小化）

```ini
# /etc/systemd/system/gscreen.service
[Unit]
Description=gScreen Slideshow
After=network.target

[Service]
Type=simple
User=rpi4
WorkingDirectory=/home/rpi4/gscreen
Environment="PYTHONUNBUFFERED=1"
Environment="PYGAME_HIDE_SUPPORT_PROMPT=1"

# 关键：将日志输出到 journald（内存），不写入文件
ExecStart=/home/rpi4/gscreen/venv/bin/python3 main.py

# 自动重启
Restart=always
RestartSec=10

# 资源限制
MemoryLimit=512M

# 定期重启服务（释放内存，保护 SD 卡）
RuntimeMaxSec=7d

[Install]
WantedBy=multi-user.target
```

### 2. Logrotate 配置（如果使用文件日志）

```bash
# /etc/logrotate.d/gscreen
/var/log/gscreen/*.log {
    daily
    rotate 3
    compress
    delaycompress
    missingok
    notifempty
    create 644 rpi4 rpi4
    # 关键：使用 copytruncate 避免重新打开文件句柄
    copytruncate
    # 限制日志大小
    size 10M
}
```

### 3. 禁用不必要的系统日志

```bash
# 编辑 /etc/systemd/journald.conf
sudo nano /etc/systemd/journald.conf

# 修改：
[Journal]
Storage=volatile  # 日志存储在内存
SystemMaxUse=50M  # 最大使用 50MB 内存
MaxFileSec=3day   # 单个日志文件最多保存 3 天
```

## 完整优化安装脚本

```bash
#!/bin/bash
# install_sd_protection.sh

echo "=== gScreen SD Card Protection Setup ==="

# 1. 创建 tmpfs 挂载点
sudo mkdir -p /dev/shm/gscreen_logs
sudo mkdir -p /dev/shm/gscreen_cache

# 2. 创建日志目录
sudo mkdir -p /var/log/gscreen
sudo chown rpi4:rpi4 /var/log/gscreen

# 3. 添加到 fstab（如果还没有）
if ! grep -q "/dev/shm/gscreen" /etc/fstab; then
    echo "tmpfs /dev/shm/gscreen_logs tmpfs defaults,noatime,size=50m 0 0" | sudo tee -a /etc/fstab
    echo "tmpfs /dev/shm/gscreen_cache tmpfs defaults,noatime,size=200m 0 0" | sudo tee -a /etc/fstab
fi

# 4. 修改 journald 配置
sudo tee /etc/systemd/journald.conf.d/gscreen.conf > /dev/null <<EOF
[Journal]
Storage=volatile
SystemMaxUse=50M
EOF

# 5. 创建健康检查脚本
cat > /home/rpi4/gscreen/check_sd_health.sh <<'SCRIPT'
#!/bin/bash
echo "=== $(date) ==="
echo "Disk usage:"
df -h /
echo "Wear level:"
cat /sys/bus/mmc/devices/*/life_time 2>/dev/null || echo "N/A"
echo "IO errors (last 10):"
sudo dmesg | grep -i "i/o error" | tail -10
echo "=== End ==="
SCRIPT
chmod +x /home/rpi4/gscreen/check_sd_health.sh

# 6. 安装监控 cron
echo "0 */6 * * * /home/rpi4/gscreen/check_sd_health.sh >> /tmp/sd_health.log 2>&1" | sudo crontab -

echo "Setup complete! Reboot recommended."
```

## 推荐的硬件方案

### 方案 A：使用 RAM 磁盘（推荐用于展示用途）
- 日志写入 /dev/shm（RAM）
- 图片缓存定期清理
- 重启后日志丢失（可接受）

### 方案 B：使用 USB 存储
- 将图片缓存移到 USB 闪存盘
- SD 卡只保留系统和程序
- USB 盘坏了容易更换

```bash
# 设置 USB 缓存
sudo mkdir -p /mnt/usb_cache
sudo mount /dev/sda1 /mnt/usb_cache
# 修改 settings.json 中的 local_cache_dir
```

### 方案 C：使用网络存储
- 图片存储在 NAS/网络共享
- 本地零写入（除了系统）

## 监控指标

| 指标 | 警告阈值 | 危险阈值 |
|------|---------|---------|
| 磁盘使用 | > 80% | > 95% |
| 磨损程度 | > 50% | > 80% |
| 温度 | > 60°C | > 70°C |
| IO 错误 | > 1/天 | > 10/天 |

## 检查清单

- [ ] 日志写入 RAM（/dev/shm）
- [ ] sync 间隔 ≥ 30 分钟
- [ ] 使用工业级 SD 卡
- [ ] 启用自动健康检查
- [ ] 设置定期服务重启（每周）
- [ ] 监控磁盘空间和磨损程度
- [ ] 准备备用 SD 卡
- [ ] 配置自动备份（重要！）

## 预期寿命计算

假设：
- 工业级 SD 卡：100,000 写入周期
- 每天写入：50MB 日志 + 100MB 图片更新 = 150MB/天
- 卡容量：32GB

**理论寿命**：
```
(32GB / 150MB) * 100,000 = 21,333 天 ≈ 58 年
```

实际寿命通常受限于：
- 控制器磨损均衡效率
- 温度和环境
- 电源稳定性

**保守估计**：5-10 年

## 紧急处理

如果发现 SD 卡损坏：
1. 立即关机，不要继续写入
2. 使用只读模式挂载复制数据
3. 更换新 SD 卡
4. 从备份恢复系统

```bash
# 只读挂载
sudo mount -o ro,remount /
# 复制数据到 USB
sudo dd if=/dev/mmcblk0 of=/mnt/usb/sdcard_backup.img bs=4M
```

## 总结

| 措施 | 效果 | 难度 |
|------|------|------|
| RAM 日志 | 减少 90% 写入 | 简单 |
| 降低 sync 频率 | 减少 80% 文件操作 | 简单 |
| 工业级 SD 卡 | 寿命延长 10 倍 | 中等 |
| 定期健康检查 | 早期发现问题 | 简单 |
| 自动备份 | 数据安全 | 中等 |

按照本指南配置后，SD 卡寿命可从 2-3 年延长至 5-10 年。
