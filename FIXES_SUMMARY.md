# 代码修复摘要

## 修复时间
2026-02-13

## 修复的问题列表

### 1. 🔴 高优先级：download.py 缩进错误
**问题**: `get_folder_contents()` 函数第53-69行有严重缩进错误，导致函数逻辑异常
**修复**: 修复了缩进，使代码块正确对齐
**文件**: `download.py`

### 2. 🔴 高优先级：视频播放 Surface 内存堆积
**问题**: 视频播放时每帧创建新的 Pygame Surface，可能导致内存碎片
**修复**: 
- 添加了 Surface 内存池 (`_surface_pool`)
- 实现了 `_get_surface_from_pool()` 和 `_return_surface_to_pool()` 方法
- 视频播放时复用 Surface 对象
**文件**: `slideshow.py`

### 3. 🔴 高优先级：图片缓存无内存限制
**问题**: 缓存仅限制数量(50张)，但高分辨率图片可能占用大量内存(50张4K图≈1.2GB)
**修复**: 
- 添加 `_max_cache_memory_mb = 100` 配置
- 修改 `_cache_image()` 方法，同时按数量和内存限制进行清理
- 添加线程锁 `_cache_lock` 确保线程安全
**文件**: `slideshow.py`

### 4. 🟡 中优先级：WiFi 信号读取过于频繁
**问题**: 每秒调用 `iwconfig` 子进程，CPU 开销大
**修复**: 
- 添加 `_wifi_signal_cache` 缓存
- 设置 30 秒缓存 TTL
- 减少子进程调用频率
**文件**: `slideshow.py`

### 5. 🟡 中优先级：子进程清理不完全
**问题**: 子进程可能成为僵尸进程
**修复**: 
- 添加 `_cleanup_process()` 静态方法
- 确保正确终止进程、等待退出、关闭管道
- 替换所有子进程清理代码
**文件**: `slideshow.py`

### 6. 🟡 中优先级：视频帧率控制失效
**问题**: 当处理时间超过帧间隔时，`wait_time` 设为 1ms，导致 CPU 100%
**修复**: 
- 修正帧率控制逻辑
- 当延迟为负时，使用 1ms 的短暂 sleep 防止 CPU 空转
**文件**: `slideshow.py`

### 7. 🟢 低优先级：错误消息不清除
**问题**: 错误消息显示 30 秒后不会被清除，每次循环都会检查
**修复**: 
- 添加自动清除逻辑
- 过期后调用 `_clear_error_message()`
**文件**: `slideshow.py`

### 8. 🟢 低优先级：时间同步返回值错误
**问题**: `_sync_time_via_ntp()` 在某些分支返回 `None` 而不是 `False`
**修复**: 确保所有分支返回布尔值
**文件**: `gdrive_sync.py`

### 9. 🟢 低优先级：缺少内存监控
**问题**: 无法了解长期运行时的内存使用情况
**修复**: 
- 添加 `_log_memory_usage()` 方法
- 每 10 分钟（约）记录一次内存使用情况
- 需要安装 `psutil` 模块: `pip install psutil`
**文件**: `slideshow.py`

## 新增依赖
```bash
pip install psutil  # 可选，用于内存监控
```

## 验证结果
```
✓ Surface 池方法已添加
✓ Surface 归还方法已添加
✓ 子进程清理方法已添加
✓ 内存日志方法已添加
✓ WiFi 信号缓存已添加
✓ 缓存锁已添加
✓ 内存限制已添加
✓ download.py 语法正确
✓ 时间同步返回值已修复
```

## 性能提升预期
1. **内存使用**: 视频播放内存分配减少 90% 以上（Surface 复用）
2. **CPU 使用**: WiFi 信号读取减少 97%（从每秒1次到每30秒1次）
3. **稳定性**: 消除僵尸进程风险
4. **缓存安全**: 防止大图片导致的 OOM

## 长期运行建议
1. 监控内存使用: `watch -n 60 'ps -o pid,rss,vsz,cmd -p $(pgrep -f "slideshow.py")'`
2. 监控僵尸进程: `watch -n 60 'ps aux | grep "^Z"'`
3. 建议每周重启一次服务（可用 systemd 定时）
4. 安装 psutil 获取详细的内存日志
