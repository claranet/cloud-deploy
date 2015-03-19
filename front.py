from flask import Flask, render_template, request, make_response
import aws_data
import instance_role
import env
import base64
import tempfile
import os
import requests
import json

def get_vpc():
   return ['vpc-12345', 'vpc-7896']


def convert_to_base64(script):
    p,buildpack_path = tempfile.mkstemp()
    buildfile = open(buildpack_path,'w')
    request.files[script].save(buildfile)
    buildfile.close
    with open(buildpack_path, "rb") as buildfile:
        result = base64.b64encode(buildfile.read())
    buildfile.close
    os.remove(buildpack_path)
    return result

app = Flask(__name__)
headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
url = 'http://localhost:5000/apps'

@app.route('/app_form')
def req():
    return render_template('app_form.html',types=aws_data.instance_type,
            roles=instance_role.role, envs=env.env, vpcs=get_vpc())


@app.route('/deploy')
def select_app():
    return render_template('select_app.html',apps=requests.get(url, headers=headers, auth=('api','api')).json()['_items'])

@app.route('/module-deploy', methods=['POST'])
def select_module():
    modules = requests.get(url+'/'+request.form['_id'], headers=headers, auth=('api','api')).json()['modules']
    code_modules=[]
    for module in modules:
        if module['scope'] == 'code':
            code_modules.append(module)
    return render_template('select_module.html',id=request.form['_id'], modules=code_modules)


@app.route('/create-job', methods=['POST'])
def create_job():
    job = {}
    job['user']='web'
    job['command']='deploy'
    job['app_id']=request.form['app-id']
    module = {}
    module['name']=request.form['module-name']
    modules = []
    modules.append(module)
    job['modules']=modules
    result = requests.post(url='http://localhost:5000/jobs',data=json.dumps(job), headers=headers, auth=('api','api'))
    resp = make_response(result.content+"</br><a href='/deploy'>return to deploy page</a>")
    return resp


@app.route('/result', methods=['POST'])
def res():
    app = {}
    module = {}
    build_infos = {}
    autoscale = {}
    if 'module-build_pack' in dict(request.files).keys():
        module['build_pack'] = convert_to_base64('module-build_pack')
    if 'module-post_deploy' in dict(request.files).keys():
        module['post_deploy'] = convert_to_base64('module-post_deploy')
    for key in request.form.keys():
        if key.find('module') >= 0:
            module[key[7:]] = request.form[key]
        elif key.find('build_infos') >= 0:
            build_infos[key[12:]] = request.form[key]
        elif key.find('autoscale')>= 0:
            autoscale[key[11:]] = request.form[key]
        else:
            app[key] = request.form[key]
    #app['autoscale'] = autoscale
    #app['build_infos'] = build_infos
    app['modules'] = [module]
    #print app
    eve_response = requests.post(url, data=json.dumps(app), headers=headers, auth=('api','api'))
    print(eve_response.content)
    resp = make_response(eve_response.content+"</br><a href='/app_form'>return</a>")
    return resp


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
