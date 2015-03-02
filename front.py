from flask import Flask, render_template, request, make_response
import aws_data
import instance_role
import env
import base64
import tempfile
import os

def get_vpc():
   return ['vpc-12345', 'vpc-7896']



app = Flask(__name__)

@app.route('/app_form')
def req():
    return render_template('app_form.html',types=aws_data.instance_type,
            roles=instance_role.role, envs=env.env, vpcs=get_vpc())


@app.route('/result', methods=['POST'])
def res():
    app = {}
    module = {}
    build_infos = {}
    autoscale = {}

    if 'module-build_pack' in dict(request.files).keys():
        p,buildpack_path = tempfile.mkstemp()
        buildfile = open(buildpack_path,'w')
        request.files['module-build_pack'].save(buildfile)
        buildfile.close
        with open(buildpack_path, "rb") as buildfile:
            module['build_pack'] = base64.b64encode(buildfile.read())
        buildfile.close
        os.remove(buildpack_path)

    for key in request.form.keys():
        if key.find('module') >= 0:
            module[key[7:]] = request.form[key]
        elif key.find('build_infos') >= 0:
            build_infos[key[12:]] = request.form[key]
        elif key.find('autoscale')>= 0:
            autoscale[key[11:]] = request.form[key]
        else:
            app[key] = request.form[key]
    app['autoscale'] = autoscale
    app['build_infos'] = build_infos
    app['modules'] = [module]
    print app
    resp = make_response("<a href='/app_form'>return</a>")
    return resp


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
