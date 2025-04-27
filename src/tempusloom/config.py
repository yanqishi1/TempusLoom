#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Configuration
Configuration management for TempusLoom
"""

import os
import sys
import json
from pathlib import Path
import logging
from PyQt6.QtCore import QSettings

logger = logging.getLogger(__name__)


class Config:
    """Configuration management for TempusLoom"""
    
    DEFAULT_CONFIG = {
        'ui': {
            'theme': 'dark',
            'language': 'zh_CN',
            'icon_size': 24,
            'recent_files_count': 10,
            'auto_save_minutes': 5,
        },
        'editing': {
            'default_format': 'jpg',
            'default_quality': 95,
            'undo_limit': 50,
            'default_dpi': 300,
        },
        'performance': {
            'use_gpu': True,
            'cache_size_mb': 1024,
            'preview_quality': 'medium',
            'thread_count': 0,  # 0 means auto
        },
        'paths': {
            'last_opened_dir': '',
            'export_dir': '',
            'plugins_dir': 'plugins',
            'presets_dir': 'presets',
        },
        'ai': {
            'enable_local_ai': True,
            'enable_cloud_ai': False,
            'api_key': '',
            'model_quality': 'medium',
        },
    }
    
    def __init__(self, config_file=None):
        """Initialize configuration
        
        Args:
            config_file (str, optional): Path to config file. If None, use default.
        """
        self.settings = QSettings()
        
        # Determine config file location
        if config_file is None:
            # Use platform-specific app data directory
            app_data_dir = self._get_app_data_dir()
            self.config_dir = Path(app_data_dir) / "TempusLoom"
            self.config_file = self.config_dir / "config.json"
        else:
            self.config_file = Path(config_file)
            self.config_dir = self.config_file.parent
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Load or create config
        self.config = self._load_config()
    
    def _get_app_data_dir(self):
        """Get platform-specific application data directory"""
        home = Path.home()
        
        if os.name == 'nt':  # Windows
            return os.getenv('APPDATA')
        elif os.name == 'posix':  # macOS/Linux
            if sys.platform == 'darwin':  # macOS
                return home / "Library" / "Application Support"
            else:  # Linux
                return os.getenv('XDG_CONFIG_HOME', home / ".config")
        else:
            # Fallback to home directory
            return home
    
    def _load_config(self):
        """Load configuration from file or create default"""
        # Start with default config
        config = self.DEFAULT_CONFIG.copy()
        
        # Try to load from file
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # Update config with loaded values
                self._update_dict(config, loaded_config)
                
                logger.info(f"Configuration loaded from {self.config_file}")
            except Exception as e:
                logger.error(f"Error loading config: {e}")
        else:
            # Save default config
            self.save()
            logger.info(f"Created default configuration at {self.config_file}")
        
        return config
    
    def _update_dict(self, target, source):
        """Recursively update dictionary"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._update_dict(target[key], value)
            else:
                target[key] = value
        return target
    
    def get(self, section, key, default=None):
        """Get configuration value
        
        Args:
            section (str): Configuration section
            key (str): Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        try:
            return self.config[section][key]
        except KeyError:
            return default
    
    def set(self, section, key, value):
        """Set configuration value
        
        Args:
            section (str): Configuration section
            key (str): Configuration key
            value: Value to set
        """
        if section not in self.config:
            self.config[section] = {}
        
        self.config[section][key] = value
    
    def save(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False 