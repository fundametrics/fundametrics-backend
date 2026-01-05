import yaml


class Config:
    _config = None

    @classmethod
    def load(cls, path="scraper/config/settings.yaml"):
        if cls._config is None:
            with open(path, "r") as f:
                cls._config = yaml.safe_load(f)
        return cls._config

    @classmethod
    def get(cls, *keys, default=None):
        cfg = cls.load()
        for key in keys:
            if not isinstance(cfg, dict):
                return default
            cfg = cfg.get(key)
        return cfg if cfg is not None else default
