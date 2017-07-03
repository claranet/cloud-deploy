from pylxd import Client as LXDClient

def list_lxd_images():
    """
    Retrieve images on local registry
    """
    lxd = LXDClient()
    images = lxd.images.all()
    image_list = {}
    image_list[''] = 'Not use container'
    for image in images:
        if image.aliases:
            alias = image.aliases[0]['name']
            for value in image.properties:
                image_list[alias] = image.properties[value]
    for image in image_list:
        return [(image, image_list[image]) for image in image_list]

def lxd_is_available():
    """
    Test if lxd is available on system
    """
    try:
        lxd = LXDClient()
    except:
        return False
    return True
