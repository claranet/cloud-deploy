from pylxd import Client as LXDClient

def list_lxd_images():
    """
    Retrieve images on local registry
    """
    if lxd_is_available():
        lxd = LXDClient()
        images = lxd.images.all()
        image_list = {}
        image_list[''] = 'Not use container'
        for image in images:
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

