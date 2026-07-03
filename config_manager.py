import json
from pathlib import Path
from datetime import datetime
from typing import Any, Optional


class ConfigManager:
    """Manages configuration and state for the application"""
    
    def __init__(self, app_name: str = "lazy-mod-manager"):
        self.app_name = app_name
        self.config_dir = Path.home() / ".config" / app_name
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Default configuration values
        self.default_config = {
            "downloads_dir": str(Path.home() / "Downloads"),
            "mods_dir": str(Path.home() / ".local/share/Steam/steamapps/compatdata/3580745457/pfx/drive_c/users/steamuser/Local Settings/Application Data/RivalsofAether/workshop"),
            "delete_mode": False,
            "auto_refresh": True,
            "theme": "gruvbox"
        }
        
        # Default state values
        self.default_state = {
            "last_selected": [],
            "last_session": datetime.now().isoformat(),
            "session_count": 0,
            "last_installed": None
        }
        
        # Load configuration and state
        self.config = self._load_config()
        self.state = self._load_state()
        
        # Update session info
        self.state["session_count"] += 1
        self.state["last_session"] = datetime.now().isoformat()
        self._save_state()
    
    def _load_config(self) -> dict:
        """Load user configuration from JSON file"""
        config_file = self.config_dir / "config.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                # Ensure all default keys exist
                for key, value in self.default_config.items():
                    if key not in config:
                        config[key] = value
                return config
            except Exception as e:
                print(f"Error loading config: {e}")
                return self.default_config.copy()
        else:
            return self.default_config.copy()
    
    def _save_config(self) -> bool:
        """Save user configuration to JSON file"""
        try:
            config_file = self.config_dir / "config.json"
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def _load_state(self) -> dict:
        """Load application state from JSON file"""
        state_file = self.config_dir / "state.json"
        
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                # Ensure all default keys exist
                for key, value in self.default_state.items():
                    if key not in state:
                        state[key] = value
                return state
            except Exception as e:
                print(f"Error loading state: {e}")
                return self.default_state.copy()
        else:
            return self.default_state.copy()
    
    def _save_state(self) -> bool:
        """Save application state to JSON file"""
        try:
            state_file = self.config_dir / "state.json"
            with open(state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving state: {e}")
            return False
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self.config.get(key, default if default is not None else self.default_config.get(key))
    
    def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value and save"""
        self.config[key] = value
        self._save_config()
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value"""
        return self.state.get(key, default if default is not None else self.default_state.get(key))
    
    def set_state(self, key: str, value: Any) -> None:
        """Set a state value and save"""
        self.state[key] = value
        self._save_state()
    
    def get_downloads_dir(self) -> Path:
        """Get downloads directory path"""
        return Path(self.get_config("downloads_dir"))
    
    def set_downloads_dir(self, path: Path) -> None:
        """Set downloads directory path"""
        self.set_config("downloads_dir", str(path))
    
    def get_mods_dir(self) -> Path:
        """Get mods directory path"""
        return Path(self.get_config("mods_dir"))
    
    def set_mods_dir(self, path: Path) -> None:
        """Set mods directory path"""
        self.set_config("mods_dir", str(path))
    
    def get_delete_mode(self) -> bool:
        """Get delete mode status"""
        return self.get_config("delete_mode", False)
    
    def set_delete_mode(self, enabled: bool) -> None:
        """Set delete mode status"""
        self.set_config("delete_mode", enabled)
    
    def save_last_selected(self, selected_items: list) -> None:
        """Save list of last selected items"""
        self.set_state("last_selected", selected_items)
    
    def get_last_selected(self) -> list:
        """Get list of last selected items"""
        return self.get_state("last_selected", [])