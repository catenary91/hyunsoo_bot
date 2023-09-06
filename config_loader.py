import json

config = {}

def load_config():
    global config
    config = json.loads(open("config.json", 'r').read())
    pass

def save_config():
    open("config.json", 'w').write(json.dumps(config, sort_keys=True, indent=2))

def get_config(guild_id, key):
    try:
        return config[str(guild_id)][str(key)]
    except:
        return None

def set_config(guild_id, key, value):
    global config
    if not str(guild_id) in config:
        config[str(guild_id)] = {}
    config[str(guild_id)][str(key)] = value
