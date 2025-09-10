#!/usr/bin/env python3
"""
Screenshot Manager for WFH Monitoring Agent
Handles desktop screenshot capture with privacy and size management
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from PIL import ImageGrab, Image
import time

class ScreenshotManager:
    def __init__(self, config_manager):
        self.config = config_manager
        self.storage_config = config_manager.get_section("local_storage")
        self.max_size_mb = self.storage_config.get("max_screenshot_size_mb", 5)
        
        # Create screenshots directory
        self.screenshots_dir = Path(__file__).parent / 'screenshots'
        self.screenshots_dir.mkdir(exist_ok=True)
        
        # Quality settings for different size requirements
        self.quality_settings = [
            {'quality': 85, 'scale': 1.0},    # High quality, full size
            {'quality': 75, 'scale': 0.8},    # Medium-high quality, 80% size
            {'quality': 65, 'scale': 0.6},    # Medium quality, 60% size
            {'quality': 55, 'scale': 0.4},    # Lower quality, 40% size
            {'quality': 45, 'scale': 0.3},    # Low quality, 30% size
        ]
        
        logging.info(f"ScreenshotManager initialized, max size: {self.max_size_mb}MB")
        
    def capture_screenshot(self, username: str) -> Optional[str]:
        """Capture desktop screenshot with automatic quality optimization"""
        try:
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = f"{username}_{timestamp}"
            
            # Capture screenshot
            screenshot = ImageGrab.grab()
            if screenshot is None:
                logging.error("Failed to capture screenshot - ImageGrab returned None")
                return None
                
            # Try different quality settings to meet size requirement
            for i, settings in enumerate(self.quality_settings):
                try:
                    filepath = self._save_with_settings(
                        screenshot, base_filename, settings, attempt=i+1
                    )
                    
                    if filepath and self._check_file_size(filepath):
                        logging.info(f"Screenshot captured: {Path(filepath).name} "
                                   f"(attempt {i+1}, quality: {settings['quality']}, "
                                   f"scale: {settings['scale']*100:.0f}%)")
                        return str(filepath)
                        
                    elif filepath:
                        # File too large, try next quality setting
                        try:
                            os.remove(filepath)
                        except:
                            pass
                        
                except Exception as e:
                    logging.debug(f"Screenshot attempt {i+1} failed: {e}")
                    continue
                    
            # If all attempts failed, save a minimal version
            logging.warning("All quality attempts failed, saving minimal screenshot")
            return self._save_minimal_screenshot(screenshot, base_filename)
            
        except Exception as e:
            logging.error(f"Screenshot capture error: {e}")
            return None
            
    def _save_with_settings(self, screenshot: Image.Image, base_filename: str, 
                           settings: dict, attempt: int) -> Optional[str]:
        """Save screenshot with specific quality settings"""
        try:
            # Scale image if needed
            if settings['scale'] < 1.0:
                original_size = screenshot.size
                new_size = (
                    int(original_size[0] * settings['scale']),
                    int(original_size[1] * settings['scale'])
                )
                screenshot = screenshot.resize(new_size, Image.Resampling.LANCZOS)
                
            # Prepare filename
            quality = settings['quality']
            scale_percent = int(settings['scale'] * 100)
            filename = f"{base_filename}_q{quality}_s{scale_percent}.jpg"
            filepath = self.screenshots_dir / filename
            
            # Save with specified quality
            screenshot.save(
                filepath, 
                'JPEG', 
                quality=quality,
                optimize=True,
                progressive=True
            )
            
            return str(filepath)
            
        except Exception as e:
            logging.error(f"Error saving screenshot with settings {settings}: {e}")
            return None
            
    def _save_minimal_screenshot(self, screenshot: Image.Image, base_filename: str) -> Optional[str]:
        """Save a very small screenshot as last resort"""
        try:
            # Extreme compression
            small_size = (320, 240)  # Very small size
            screenshot = screenshot.resize(small_size, Image.Resampling.LANCZOS)
            
            filename = f"{base_filename}_minimal.jpg"
            filepath = self.screenshots_dir / filename
            
            screenshot.save(
                filepath, 
                'JPEG', 
                quality=30,
                optimize=True
            )
            
            if self._check_file_size(filepath):
                logging.info(f"Minimal screenshot saved: {filename}")
                return str(filepath)
            else:
                logging.error("Even minimal screenshot is too large")
                try:
                    os.remove(filepath)
                except:
                    pass
                return None
                
        except Exception as e:
            logging.error(f"Error saving minimal screenshot: {e}")
            return None
            
    def _check_file_size(self, filepath: str) -> bool:
        """Check if file size is within limits"""
        try:
            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            return file_size_mb <= self.max_size_mb
        except Exception as e:
            logging.error(f"Error checking file size: {e}")
            return False
            
    def cleanup_old_screenshots(self, days: int = 7) -> int:
        """Clean up old screenshot files"""
        try:
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            deleted_count = 0
            
            for filepath in self.screenshots_dir.iterdir():
                if filepath.is_file() and filepath.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    try:
                        if filepath.stat().st_mtime < cutoff_time:
                            filepath.unlink()
                            deleted_count += 1
                    except Exception as e:
                        logging.debug(f"Error deleting old screenshot {filepath}: {e}")
                        
            if deleted_count > 0:
                logging.info(f"Cleaned up {deleted_count} old screenshots")
                
            return deleted_count
            
        except Exception as e:
            logging.error(f"Error during screenshot cleanup: {e}")
            return 0
            
    def get_storage_stats(self) -> dict:
        """Get screenshot storage statistics"""
        try:
            stats = {
                'total_files': 0,
                'total_size_mb': 0,
                'avg_size_mb': 0,
                'oldest_file': None,
                'newest_file': None
            }
            
            files_info = []
            
            for filepath in self.screenshots_dir.iterdir():
                if filepath.is_file() and filepath.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    try:
                        stat = filepath.stat()
                        size_mb = stat.st_size / (1024 * 1024)
                        
                        files_info.append({
                            'path': filepath,
                            'size_mb': size_mb,
                            'mtime': stat.st_mtime
                        })
                        
                    except Exception as e:
                        logging.debug(f"Error getting stats for {filepath}: {e}")
                        
            if files_info:
                stats['total_files'] = len(files_info)
                stats['total_size_mb'] = round(sum(f['size_mb'] for f in files_info), 2)
                stats['avg_size_mb'] = round(stats['total_size_mb'] / stats['total_files'], 2)
                
                # Find oldest and newest
                sorted_by_time = sorted(files_info, key=lambda x: x['mtime'])
                stats['oldest_file'] = sorted_by_time[0]['path'].name
                stats['newest_file'] = sorted_by_time[-1]['path'].name
                
            return stats
            
        except Exception as e:
            logging.error(f"Error getting storage stats: {e}")
            return {}
            
    def verify_screenshot_quality(self, filepath: str) -> dict:
        """Verify screenshot can be opened and get basic info"""
        try:
            with Image.open(filepath) as img:
                return {
                    'valid': True,
                    'size': img.size,
                    'mode': img.mode,
                    'format': img.format,
                    'file_size_mb': round(os.path.getsize(filepath) / (1024 * 1024), 2)
                }
        except Exception as e:
            logging.error(f"Screenshot verification failed for {filepath}: {e}")
            return {
                'valid': False,
                'error': str(e)
            }