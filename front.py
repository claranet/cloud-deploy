from flask import Flask, render_template, request, make_response
import aws_data
import instance_role
import env


def get_vpc():
   return ['vpc-12345', 'vpc-7896']



app = Flask(__name__)

@app.route('/app_form')
def app_form():
    return render_template('app_form.html',types=aws_data.instance_type,
            roles=instance_role.role, envs=env.env, vpcs=get_vpc())

@app.route('/result', methods=['POST'])
def response():
    print request.form
    print request.form.__dict__
    print request.json
    print request.__dict__
    resp = make_response("<a href='/app_form'>return</a>")
    return resp


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
