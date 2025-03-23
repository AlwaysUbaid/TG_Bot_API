# Configuration handling
"""Configuration manager for Elysium Trading Platform"""

import os
import json
import logging
import hashlib
from typing import Any, Dict, List, Optional, Union

class ConfigManager:
    """Handles configuration storage and retrieval"""
    
    DEFAULT_CONFIG_PATH = "config.json"
    
    def __init__(self, config_path: str = None):
        """
        Initialize configuration manager
        
        Args:
            config_path: Path to configuration file (default: config.json)
        """
        self.logger = logging.getLogger(__name__)
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = {}
        
        # Load configuration
        self.load_config()
    
    def load_config(self) -> bool:
        """
        Load configuration from file
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
                self.logger.info(f"Loaded configuration from {self.config_path}")
                return True
            else:
                self.logger.warning(f"Configuration file {self.config_path} not found, using defaults")
                self.config = {}
                return False
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            self.config = {}
            return False
    
    def save_config(self) -> bool:
        """
        Save configuration to file
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            self.logger.info(f"Saved configuration to {self.config_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """
        Set configuration value
        
        Args:
            key: Configuration key
            value: Configuration value
            
        Returns:
            True if saved successfully, False otherwise
        """
        self.config[key] = value
        return self.save_config()
    
    def delete(self, key: str) -> bool:
        """
        Delete configuration key
        
        Args:
            key: Configuration key
            
        Returns:
            True if deleted and saved successfully, False otherwise
        """
        if key in self.config:
            del self.config[key]
            return self.save_config()
        return True  # Key didn't exist, so technically it's deleted
    
    def clear(self) -> bool:
        """
        Clear all configuration
        
        Returns:
            True if cleared and saved successfully, False otherwise
        """
        self.config = {}
        return self.save_config()
    
    def set_password(self, password: str) -> bool:
        """
        Set password hash in configuration
        
        Args:
            password: Password to hash and store
            
        Returns:
            True if saved successfully, False otherwise
        """
        # Generate a salt
        salt = os.urandom(16).hex()
        
        # Hash the password with the salt
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        
        # Store password hash and salt
        self.config["password_hash"] = password_hash
        self.config["password_salt"] = salt
        
        return self.save_config()
    
    def verify_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash
        
        Args:
            password: Password to verify
            
        Returns:
            True if password is correct, False otherwise
        """
        stored_hash = self.config.get("password_hash")
        salt = self.config.get("password_salt")
        
        if not stored_hash or not salt:
            self.logger.warning("No password hash or salt found in configuration")
            return False
        
        # Hash the provided password with the stored salt
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        
        # Compare with the stored hash
        return password_hash == stored_hash