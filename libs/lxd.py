from pylxd import Client as LXDClient

def list_lxd_images():
    """
    Retrieve images on local registry
    """
    if lxd_is_available():

        # container_config = config.get('container', {'endpoint': self._config.get('endpoint', 'localhost'),
        #                                                         'debug': self._config.get('debug', False),
        #                                                        })
        #container_config = "https://images.linuxcontainers.org"
        container_config = "localhost"
        if container_config == "localhost":
            lxd = LXDClient()
        else:
            lxd = LXDClient(endpoint=container_config, verify=False)
        images = lxd.images.all()
        

        image_list = {}
        image_list[''] = 'Not use container'
        #return [('','Container Image list is unvailable, check your LXD parameters in config.yml')]
        for image in images:
                print image.fingerprint
                fingerprint = image.fingerprint
                for value in image.properties:
                    image_list[fingerprint] = image.properties['description']
        for image in image_list:
            return [(image, image_list[image]) for image in image_list]
    else:
        return [('','Container Image list is unvailable, check your LXD parameters in config.yml')]

def lxd_is_available():
    """
    Test if lxd is available on system
    """
    try:
        lxd = LXDClient()
    except:
        return False
    return True

