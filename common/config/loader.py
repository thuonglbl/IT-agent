"""
Multi-format Configuration Loader
Supports YAML (folder 03 style) and Python modules (folders 01/02 style)
Auto-detects format and merges with environment variables
"""
import os
import sys
import importlib.util
import yaml


class ConfigLoader:
    """
    Multi-format configuration loader.

    Supports:
    - YAML files (config.yaml)
    - Environment variable overrides
    - Optional validation
    """

    def __init__(self, config_path=None, validate=True):
        """
        Initialize config loader.

        Args:
            config_path: Path to config file (auto-detected if None)
            validate: Validate configuration (default: True)
        """
        self.config_path = config_path
        self.validate = validate

    def load(self):
        """
        Load configuration from file with auto-detection.

        Supports configuration inheritance:
        1. Loads common/config.yaml (if exists) as base configuration
        2. Loads folder-specific config.yaml
        3. Deep merges folder config over common config
        4. Merges environment variables (highest priority)

        Returns:
            dict: Merged configuration dictionary

        Raises:
            FileNotFoundError: If config file not found
            ValueError: If validation fails
        """
        # Load common configuration (if exists)
        common_config = self._load_common_config()

        # Load folder-specific configuration
        folder_config = self._load_folder_config()

        # Deep merge: folder config overrides common config
        config = self._deep_merge(common_config, folder_config)

        # Merge environment variables (highest priority)
        config = self._merge_env_vars(config)

        # Resolve relative paths (SSL certificates, etc.)
        config = self._resolve_paths(config)

        # Validate if enabled
        if self.validate:
            self._validate_config(config)

        return config

    def _load_common_config(self):
        """
        Load common configuration from common/config.yaml.

        Returns:
            dict: Common configuration, or empty dict if not found
        """
        # Check for common/config.yaml relative to current directory
        common_config_path = os.path.join('common', 'config.yaml')

        # Also check parent directory (for scripts in subfolders)
        parent_common_config_path = os.path.join('..', 'common', 'config.yaml')

        if os.path.exists(common_config_path):
            print(f"Loading common config: {common_config_path}")
            with open(common_config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        elif os.path.exists(parent_common_config_path):
            print(f"Loading common config: {parent_common_config_path}")
            with open(parent_common_config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        else:
            # No common config found - return empty dict
            return {}

    def _load_folder_config(self):
        """
        Load folder-specific configuration.

        Returns:
            dict: Folder-specific configuration

        Raises:
            FileNotFoundError: If config file not found
            ValueError: If validation fails
        """
        # Auto-detect config file if not specified
        if self.config_path is None:
            self.config_path = self._auto_detect_config()

        # Load based on file extension
        if self.config_path.endswith('.yaml') or self.config_path.endswith('.yml'):
            config = self._load_yaml()
        elif self.config_path.endswith('.py'):
            config = self._load_python_module()
        else:
            raise ValueError(f"Unsupported config format: {self.config_path}")

        return config

    def _deep_merge(self, base, override):
        """
        Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary (takes precedence)

        Returns:
            dict: Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override value
                result[key] = value

        return result

    def _auto_detect_config(self):
        """
        Auto-detect configuration file.

        Priority:
        1. config.yaml
        2. config.yml
        3. config.py

        Returns:
            str: Path to config file

        Raises:
            FileNotFoundError: If no config file found
        """
        candidates = ['config.yaml', 'config.yml', 'config.py']

        for candidate in candidates:
            if os.path.exists(candidate):
                print(f"Auto-detected config: {candidate}")
                return candidate

        raise FileNotFoundError(
            f"Configuration file not found. Tried: {', '.join(candidates)}\n"
            f"Please create one of these files with your configuration."
        )

    def _load_yaml(self):
        """
        Load YAML configuration file.

        Returns:
            dict: Configuration dictionary

        Raises:
            FileNotFoundError: If config file not found
            yaml.YAMLError: If YAML is invalid
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please copy config.yaml.example to config.yaml and update with your settings."
            )

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if config is None:
            raise ValueError(f"Configuration file is empty: {self.config_path}")

        return config

    def _load_python_module(self):
        """
        Load Python module configuration.

        Returns:
            dict: Configuration dictionary extracted from module attributes

        Raises:
            FileNotFoundError: If config file not found
            ImportError: If module cannot be imported
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create config.py with your configuration."
            )

        # Load module dynamically
        spec = importlib.util.spec_from_file_location("config_module", self.config_path)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)

        # Extract configuration attributes
        # Support both flat attributes and nested dicts
        config = {}

        # Check if module has a 'CONFIG' dict (structured approach)
        if hasattr(config_module, 'CONFIG'):
            return config_module.CONFIG

        # Otherwise, extract attributes by convention
        # Look for common prefixes: JIRA_, GLPI_, etc.
        for attr in dir(config_module):
            if attr.isupper() and not attr.startswith('_'):
                value = getattr(config_module, attr)

                # Parse attribute name (e.g., JIRA_URL -> jira.url)
                if '_' in attr:
                    parts = attr.lower().split('_', 1)
                    section = parts[0]
                    key = parts[1]

                    if section not in config:
                        config[section] = {}
                    config[section][key] = value
                else:
                    # Top-level attribute
                    config[attr.lower()] = value

        return config

    def _resolve_paths(self, config):
        """
        Resolve relative file paths to absolute paths.

        Resolves paths relative to the repository root directory.
        This ensures SSL certificates and other files can be found
        regardless of which subfolder the script runs from.

        Args:
            config: Configuration dictionary

        Returns:
            dict: Configuration with resolved absolute paths
        """
        # Find repository root (where common/ folder is located)
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

        # Resolve GLPI SSL certificate path
        if 'glpi' in config:
            verify_ssl = config['glpi'].get('verify_ssl')
            if isinstance(verify_ssl, str) and not os.path.isabs(verify_ssl):
                # Convert relative path to absolute
                abs_path = os.path.join(repo_root, verify_ssl)
                if os.path.exists(abs_path):
                    config['glpi']['verify_ssl'] = abs_path
                    print(f"Resolved SSL certificate path: {abs_path}")

        # Resolve Jira SSL certificate path
        if 'jira' in config:
            verify_ssl = config['jira'].get('verify_ssl')
            if isinstance(verify_ssl, str) and not os.path.isabs(verify_ssl):
                # Convert relative path to absolute
                abs_path = os.path.join(repo_root, verify_ssl)
                if os.path.exists(abs_path):
                    config['jira']['verify_ssl'] = abs_path
                    print(f"Resolved Jira SSL certificate path: {abs_path}")

        return config

    def _merge_env_vars(self, config):
        """
        Merge environment variables into configuration.

        Environment variables take precedence over file values.

        Supported environment variables:
            - JIRA_PAT: Jira Personal Access Token
            - JIRA_URL: Jira server URL
            - GLPI_APP_TOKEN: GLPI application token
            - GLPI_USER_TOKEN: GLPI user token
            - GLPI_USERNAME: GLPI username
            - GLPI_PASSWORD: GLPI password
            - LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        Args:
            config: Configuration dictionary

        Returns:
            dict: Configuration with environment variables merged
        """
        # Jira environment variables
        if 'JIRA_PAT' in os.environ:
            config.setdefault('jira', {})['pat'] = os.environ['JIRA_PAT']

        if 'JIRA_URL' in os.environ:
            config.setdefault('jira', {})['url'] = os.environ['JIRA_URL']

        # GLPI environment variables
        if 'GLPI_APP_TOKEN' in os.environ:
            config.setdefault('glpi', {})['app_token'] = os.environ['GLPI_APP_TOKEN']

        if 'GLPI_USER_TOKEN' in os.environ:
            config.setdefault('glpi', {})['user_token'] = os.environ['GLPI_USER_TOKEN']

        if 'GLPI_USERNAME' in os.environ:
            config.setdefault('glpi', {})['username'] = os.environ['GLPI_USERNAME']

        if 'GLPI_PASSWORD' in os.environ:
            config.setdefault('glpi', {})['password'] = os.environ['GLPI_PASSWORD']

        # Logging environment variable
        if 'LOG_LEVEL' in os.environ:
            config.setdefault('logging', {})['level'] = os.environ['LOG_LEVEL']

        return config

    def _validate_config(self, config):
        """
        Validate that required configuration fields exist.

        Args:
            config: Configuration dictionary

        Raises:
            ValueError: If required fields are missing
        """
        errors = []

        # Validate Jira config (if present)
        if 'jira' in config:
            jira = config['jira']
            if not jira.get('url'):
                errors.append("Missing 'jira.url' in config")
            if not jira.get('pat') and not jira.get('token'):
                errors.append("Missing 'jira.pat' (or 'jira.token') in config")

        # Validate GLPI config
        if 'glpi' in config:
            glpi = config['glpi']
            if not glpi.get('url'):
                errors.append("Missing 'glpi.url' in config")
            if not glpi.get('app_token'):
                errors.append("Missing 'glpi.app_token' in config")

            # Check that either user_token or (username + password) is provided
            has_user_token = glpi.get('user_token')
            has_credentials = glpi.get('username') and glpi.get('password')

            if not has_user_token and not has_credentials:
                errors.append(
                    "Missing GLPI authentication: provide either 'glpi.user_token' "
                    "or both 'glpi.username' and 'glpi.password'"
                )

        # Raise errors if any
        if errors:
            error_message = "Configuration validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
            raise ValueError(error_message)


# Convenience function for backward compatibility
def load_config(config_path=None, validate=True):
    """
    Load configuration (convenience function).

    Args:
        config_path: Path to config file (auto-detected if None)
        validate: Validate configuration (default: True)

    Returns:
        dict: Merged configuration dictionary
    """
    loader = ConfigLoader(config_path=config_path, validate=validate)
    return loader.load()
