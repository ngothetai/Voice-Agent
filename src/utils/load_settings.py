import yaml


def load_settings(file_path: str) -> dict:
    with open(file_path, 'r') as file:
        settings = yaml.safe_load(file)
    return settings
