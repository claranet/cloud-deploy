import pkgutil

from flask import jsonify
from flask import Blueprint

from eve.auth import requires_auth
from libs.lxd import lxd_is_available, list_lxd_images
lxd_blueprint = Blueprint('lxd_blueprint', __name__)

@lxd_blueprint.route('/lxd/status', methods=['GET'])
def lxd_status():
    return jsonify([ ("status", str(lxd_is_available())) ])

@lxd_blueprint.route('/lxd/images', methods=['GET'])
def list_images():
    return jsonify(list_lxd_images())
