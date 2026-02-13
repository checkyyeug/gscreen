#!/usr/bin/env python3
"""
SD Card Protection Module
Manages write operations to extend SD card lifespan
"""

import os
import json
import logging
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class SDProtectionConfig:
    """Configuration for SD card protection"""
    # Log management
    max_log_size_mb: int = 10
    max_log_backups: int = 3
    log_to_memory: bool = False  # Log to RAM instead of SD card
    
    # Sync optimization
    min_sync_interval_minutes: int = 5  # Minimum time between syncs
    enable_incremental_sync: bool = True  # Only sync changed files
    
    # Cache management
    cache_dir_on_tmpfs: bool = False  # Use RAM for cache if possible
    max_cache_age_days: int = 30  # Delete cache files older than this
    
    # Wear leveling simulation
    wear_leveling_dir: Optional[str] = None  # Directory for wear leveling
    
    # State file management
    state_file_max_writes_per_day: int = 100


class SDProtectionManager:
    """Manages SD card write operations to minimize wear"""
    
    def __init__(self, config: Optional[SDProtectionConfig] = None):
        self.config = config or SDProtectionConfig()
        self._write_count = 0
        self._write_log: Dict[str, int] = {}
        self._last_sync_time: Optional[datetime] = None
        self._state_cache: Dict[str, Any] = {}
        self._state_dirty = False
        self._last_state_save = datetime.now()
        
    def setup_ram_logging(self) -> bool:
        """Setup logging to RAM (/dev/shm) instead of SD card"""
        if not self.config.log_to_memory:
            return False
            
        ram_log_dir = Path("/dev/shm/gscreen_logs")
        try:
            ram_log_dir.mkdir(parents=True, exist_ok=True)
            
            # Setup rotating file handler in RAM
            from logging.handlers import RotatingFileHandler
            
            log_file = ram_log_dir / "gscreen.log"
            handler = RotatingFileHandler(
                log_file,
                maxBytes=self.config.max_log_size_mb * 1024 * 1024,
                backupCount=self.config.max_log_backups
            )
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            
            # Add to root logger
            root_logger = logging.getLogger()
            root_logger.addHandler(handler)
            
            logger.info(f"Logging to RAM: {log_file}")
            return True
        except Exception as e:
            logger.warning(f"Could not setup RAM logging: {e}")
            return False
    
    def should_sync(self, force: bool = False) -> bool:
        """Check if sync should be performed based on rate limiting"""
        if force:
            return True
            
        if self._last_sync_time is None:
            return True
            
        elapsed = datetime.now() - self._last_sync_time
        min_interval = timedelta(minutes=self.config.min_sync_interval_minutes)
        
        if elapsed < min_interval:
            logger.debug(f"Sync throttled. Last sync: {elapsed.seconds}s ago")
            return False
            
        return True
    
    def record_sync(self):
        """Record that a sync was performed"""
        self._last_sync_time = datetime.now()
        self._write_count += 1
    
    def optimize_cache_dir(self, cache_dir: str) -> str:
        """Return optimized cache directory (possibly on tmpfs)"""
        cache_path = Path(cache_dir)
        
        if self.config.cache_dir_on_tmpfs:
            # Try to use /dev/shm (RAM) for cache
            tmpfs_cache = Path("/dev/shm/gscreen_cache")
            try:
                tmpfs_cache.mkdir(parents=True, exist_ok=True)
                
                # Create symlink from original cache to tmpfs
                if cache_path.exists() and not cache_path.is_symlink():
                    # Backup existing cache
                    backup = Path(str(cache_path) + ".backup")
                    import shutil
                    if backup.exists():
                        shutil.rmtree(backup)
                    shutil.move(str(cache_path), str(backup))
                    
                if not cache_path.exists():
                    cache_path.symlink_to(tmpfs_cache)
                    
                logger.info(f"Cache optimized: {cache_path} -> {tmpfs_cache}")
                return str(tmpfs_cache)
            except Exception as e:
                logger.warning(f"Could not optimize cache: {e}")
                
        return str(cache_path.resolve())
    
    def cleanup_old_cache(self, cache_dir: str) -> int:
        """Remove cache files older than max_cache_age_days"""
        cache_path = Path(cache_dir)
        if not cache_path.exists():
            return 0
            
        max_age = timedelta(days=self.config.max_cache_age_days)
        now = datetime.now()
        removed = 0
        
        try:
            for file in cache_path.iterdir():
                if file.is_file():
                    mtime = datetime.fromtimestamp(file.stat().st_mtime)
                    if now - mtime > max_age:
                        try:
                            file.unlink()
                            removed += 1
                            logger.debug(f"Removed old cache file: {file.name}")
                        except Exception as e:
                            logger.warning(f"Could not remove {file}: {e}")
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
            
        if removed > 0:
            logger.info(f"Cache cleanup: removed {removed} old files")
            
        return removed
    
    def load_state(self, state_file: str) -> Dict[str, Any]:
        """Load state from file with caching"""
        if self._state_cache:
            return self._state_cache.copy()
            
        state_path = Path(state_file)
        if not state_path.exists():
            return {}
            
        try:
            with open(state_file, 'r') as f:
                self._state_cache = json.load(f)
            return self._state_cache.copy()
        except Exception as e:
            logger.error(f"Could not load state: {e}")
            return {}
    
    def save_state(self, state_file: str, state: Dict[str, Any], force: bool = False) -> bool:
        """Save state to file with write coalescing"""
        self._state_cache = state.copy()
        
        if not force:
            # Check if we should throttle writes
            now = datetime.now()
            elapsed = now - self._last_state_save
            
            if elapsed < timedelta(seconds=60):  # Max 1 write per minute
                self._state_dirty = True
                return False  # Deferred
                
        # Check daily write limit
        today = datetime.now().strftime("%Y-%m-%d")
        daily_writes = self._write_log.get(today, 0)
        
        if daily_writes >= self.config.state_file_max_writes_per_day:
            logger.warning(f"Daily state write limit reached ({daily_writes})")
            return False
        
        try:
            # Write to temp file first, then move (atomic)
            state_path = Path(state_file)
            temp_file = state_path.with_suffix('.tmp')
            
            with open(temp_file, 'w') as f:
                json.dump(state, f)
                
            temp_file.replace(state_path)
            
            self._last_state_save = datetime.now()
            self._state_dirty = False
            self._write_log[today] = daily_writes + 1
            
            logger.debug(f"State saved: {state_file}")
            return True
            
        except Exception as e:
            logger.error(f"Could not save state: {e}")
            return False
    
    def get_write_stats(self) -> Dict[str, Any]:
        """Get write operation statistics"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        return {
            "total_writes": self._write_count,
            "daily_writes": self._write_log.get(today, 0),
            "state_dirty": self._state_dirty,
            "last_sync": self._last_sync_time.isoformat() if self._last_sync_time else None,
            "last_state_save": self._last_state_save.isoformat()
        }
    
    def sync_state_if_dirty(self, state_file: str) -> bool:
        """Force save state if there are pending changes"""
        if self._state_dirty:
            return self.save_state(state_file, self._state_cache, force=True)
        return True


class SDCardHealthMonitor:
    """Monitor SD card health"""
    
    def __init__(self):
        self._last_check = None
        self._health_data = {}
    
    def check_health(self) -> Dict[str, Any]:
        """Check SD card health metrics"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "sd_card_available": False,
            "disk_usage": None,
            "wear_level": None,
            "temperature": None
        }
        
        try:
            # Check disk usage
            import shutil
            stat = shutil.disk_usage("/")
            result["disk_usage"] = {
                "total_gb": stat.total / (1024**3),
                "used_gb": stat.used / (1024**3),
                "free_gb": stat.free / (1024**3),
                "percent": (stat.used / stat.total) * 100
            }
            result["sd_card_available"] = True
            
            # Try to get SD card wear level (if available via mmc)
            wear_level = self._read_wear_level()
            if wear_level is not None:
                result["wear_level"] = wear_level
                
            # Check if running on tmpfs/RAM
            result["tmpfs_available"] = Path("/dev/shm").exists()
            
            self._health_data = result
            self._last_check = datetime.now()
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            
        return result
    
    def _read_wear_level(self) -> Optional[int]:
        """Try to read SD card wear level from system"""
        try:
            # Try to find mmc device
            for device in Path("/sys/bus/mmc/devices").glob("*"):
                life_time = device / "life_time"
                if life_time.exists():
                    # 0x01 = 0-10% worn, 0x0A = 90-100% worn
                    value = int(life_time.read_text().strip(), 16)
                    return min(100, value * 10)  # Convert to percentage
        except Exception:
            pass
        return None
    
    def is_healthy(self) -> bool:
        """Check if SD card is healthy"""
        health = self.check_health()
        
        if not health["sd_card_available"]:
            return False
            
        # Check disk space
        if health["disk_usage"]:
            if health["disk_usage"]["percent"] > 95:
                logger.warning("SD card is nearly full!")
                return False
                
        # Check wear level
        if health["wear_level"] is not None:
            if health["wear_level"] > 80:
                logger.warning(f"SD card wear level high: {health['wear_level']}%")
                return False
                
        return True


def setup_sd_protection() -> SDProtectionManager:
    """Setup SD card protection with default configuration"""
    config = SDProtectionConfig(
        max_log_size_mb=10,
        max_log_backups=2,
        log_to_memory=True,  # Log to RAM
        min_sync_interval_minutes=5,
        cache_dir_on_tmpfs=False,  # Set to True if you have enough RAM
        max_cache_age_days=30,
        state_file_max_writes_per_day=100
    )
    
    manager = SDProtectionManager(config)
    
    # Setup RAM logging
    manager.setup_ram_logging()
    
    logger.info("SD card protection initialized")
    return manager


if __name__ == "__main__":
    # Test
    manager = setup_sd_protection()
    
    # Check health
    monitor = SDCardHealthMonitor()
    health = monitor.check_health()
    print(f"SD Card Health: {health}")
    
    print(f"Write stats: {manager.get_write_stats()}")
