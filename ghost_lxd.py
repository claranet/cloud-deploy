from flask import Blueprint
from flask import jsonify

from ghost_tools import config
from libs.lxd import lxd_is_available, list_lxd_images


lxd_blueprint = Blueprint('lxd_blueprint', __name__)


@lxd_blueprint.route('/lxd/status', methods=['GET'])
def lxd_status():
    return jsonify({"status": lxd_is_available(config)})


@lxd_blueprint.route('/lxd/images', methods=['GET'])
def list_images():
    return jsonify(list_lxd_images(config))
