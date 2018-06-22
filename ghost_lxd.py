from flask import Blueprint
from flask import abort, jsonify

from ghost_tools import config
from libs.lxd import lxd_is_available, list_lxd_images


lxd_blueprint = Blueprint('lxd_blueprint', __name__)


@lxd_blueprint.route('/lxd/status', methods=['GET'])
def lxd_status():
  try:
    return jsonify({'status': lxd_is_available(config)})
  except Exception as e:
    return jsonify({'status': False, 'error': type(e).__name__})


@lxd_blueprint.route('/lxd/images', methods=['GET'])
def list_images():
  try:
    return jsonify(list_lxd_images(config))
  except Exception as e:
    return jsonify({'images': [('', 'Container Image list is unavailable, check your LXD parameters in config.yml')], 'error': type(e).__name__})
