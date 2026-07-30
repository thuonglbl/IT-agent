import os
import json

class IdMappingManager:
    """
    Manages the mapping between Jira IDs/Keys and GLPI IDs.
    """
    def __init__(self, map_file='jira_glpi_id_map.json'):
        self.map_file = map_file
        self.mapping = self.load()

    def load(self):
        if os.path.exists(self.map_file):
            with open(self.map_file, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def save(self):
        with open(self.map_file, 'w', encoding='utf-8') as f:
            json.dump(self.mapping, f, indent=2)

    def add_mapping(self, jira_key, glpi_id):
        self.mapping[jira_key] = glpi_id
        self.save()

    def get_glpi_id(self, jira_key):
        return self.mapping.get(jira_key)

    def get_all(self):
        return self.mapping
