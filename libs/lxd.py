from pylxd import Client as LXDClient


def list_lxd_images(config=None):
    """
    Retrieve images on local registry
    """
    config = config or {}
    if lxd_is_available(config):
        container_config = config.get('container', {'endpoint': config.get('endpoint',
                                                                           'https://lxd.ghost.morea.fr:8443')})
        if container_config.get('endpoint', 'localhost') == "localhost":
            lxd = LXDClient()
        else:
            lxd = LXDClient(endpoint=container_config.get('endpoint', 'https://lxd.ghost.morea.fr:8443'), verify=True)
        images = lxd.images.all()

        return [('', "Don't use containers")] + \
               [(image.fingerprint,
                 '{} - {}'.format(image.properties.get('description'), ','.join([a['name'] for a in image.aliases])))
                for image in images]
    else:
        return [('', 'Container Image list is unavailable, check your LXD parameters in config.yml')]


def lxd_is_available(config=None):
    """
    Test if lxd is available on system and test if remote lxd endpoint is available
    """
    config = config or {}
    try:
        lxd_local = LXDClient()
        container_config = config.get('container', {'endpoint': config.get('endpoint',
                                                                           'https://lxd.ghost.morea.fr:8443')})
        if container_config.get('endpoint', 'localhost') != "localhost":
            lxd = LXDClient(endpoint=container_config.get('endpoint', 'https://lxd.ghost.morea.fr:8443'), verify=True)
    except:
        return False
    return True
