from ghost_log import log
from ghost_tools import GCallException, get_provisioners_config

from .provisioner import FeaturesProvisioner
from .provisioner_salt import FeaturesProvisionerSalt
from .provisioner_ansible import FeaturesProvisionerAnsible


def get_provisioners(config, log_file, unique, job_options, app):
    """
    Factory function to instantiate the right implementation Class

    :param config: YAML Config object
    :param log_file: Log file stream
    :param unique: Unique ID
    :param job_options: Job parameters
    :param app: Ghost Application

    :return: a FeaturesProvisioner sub-class object list
    """
    ret = []
    provisioners_config = get_provisioners_config(config)
    for key, provisioner_config in provisioners_config.iteritems():
        if key == 'salt':
            ret.append(FeaturesProvisionerSalt(log_file, unique, job_options, provisioner_config, config))
        elif key == 'ansible':
            ret.append(FeaturesProvisionerAnsible(log_file, unique, app['build_infos']['ssh_username'], provisioner_config, config))
        else:
            log("Invalid provisioner type. Please check your yaml 'config.yml' file", log_file)
            raise GCallException("Invalid features provisioner type")

    return ret
