import os
import yaml

def test_sample_config_yaml():
    with open(os.path.dirname(os.path.realpath(__file__)) + '/../config.yml.sample', 'r') as conf_file:
        config = yaml.load(conf_file)
        assert 'ghost_base_url' in config
