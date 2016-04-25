"""

    Modules to easily perform requests on the Haproxy API(Hapi).
    Supported features:
        * Retrieve backends with their instances.
        * Check if difference exist between multiple Haproxy configuration.
        * Check that there is no instance in maintenance mode or down in a backend.
        * Disable or enable instances in an Haproxy backend.
        * Do post requests on Hapi.
        * Enable or disable the deployment mode of Haproxy.
        * Do a switch between two backends.
        * Remove the instance(s) from an Haproxy backend.
        * Add the instance(s) from an Haproxy backend.


"""
# -*- coding: utf-8 -*-
#!/usr/bin/env python
import debug
import requests
import json
import itertools

class Haproxyapi:
    """A lightweight class for interraction with Hapi, an API for HAproxy"""

    def __init__(self, haproxy_ips = [], hapi_port = '5001', timeout = 3, retry = 3):
        """ Initialize the variable to communicate with Hapi an Haproxy API.

            :param  haproxy_ips: list of Haproxy IPs.
            :param  hapi_port: string or int of the Hapi port.
            :param  timeout: int the default timeout for each request on the API.
            :param  retry: int maximum retry for each request on the API.
        """
        self.headers = {'content-type': 'application/json'}
        self._urls = ['http://{0}:{1}/haproxy' .format(ip, str(hapi_port)) for ip in haproxy_ips]
        self._timeout = int(timeout)
        requests.adapters.DEFAULT_RETRIES = int(retry)

    def get_haproxy_urls(self):
        """ Returns a list of Haproxy URls

            :return list of Haproxy URLs
        """
        return self._urls

    def check_haproxy_conf(self, haproxy_conf = []):
        """ Do the difference between Haproxy's configuration.

            :param   haproxy_conf: list of Haproxy configurations(backend with instances IPs).
            :return  boolean (True if conf are equal otherwise False)
        """
        _diff = 0
        for a, b in itertools.combinations(haproxy_conf, 2):
            _diff += cmp(a, b)
        if not _diff:
            return True
        return False

    def check_all_instances_up(self, backend_name, haproxy_conf):
        """ Return False if at least one instance is in maintenance mode or down in the backend in parameter,
            otherwise return True.

            :param   backend_name  string: The name of the Haproxy backend to check.
            :param   haproxy_conf: dict of the Haproxy configuration.
            :return  Boolean
        """
        for instance in haproxy_conf[backend_name]:
            if instance['status'] == 'maint' or instance['status'] == 'down':
                return False
        return True


    def get_haproxy_conf(self, haproxy_url, expand = False):
        """ Retrieve the configuration(IPs list per backend) of the Haproxy or
            the full instance informations if the parameter expand is set to True.

            :param   haproxy_url: string of the Haproxy url(only one url)
            :param   expand: bool  if set to True return a full description of the instance.
            :return  a dictionary * of all backends as key and his instances as value(list) if expand is set to False
                                  * of all backends as key and the full description of the instance as value(dict) if
                                    expand is set to True(ex: {'backend_name':[{'ip':xxx,'name':'xxx','status':'up'},...]})
        """
        haproxy_conf = {}
        for backend in requests.get(haproxy_url + '?show').json().values()[0]:
            if expand:
                haproxy_conf[backend] = requests.get(haproxy_url + '?show={0}' .format(backend)).json().values()[0]
            else:
                haproxy_conf[backend] = [ip['ip'].split(':')[0] for ip in requests.get(haproxy_url + '?show={0}' .format(backend)).json().values()[0]]
        return haproxy_conf

    def hapi_post_request(self, datas):
        """ Perform Post requests on Haproxy APIs.

            :param   datas: a dictionnary of the datas to send.
            :return  boolean (True if all requests succeed otherwise False).
        """
        for haproxy_url in self._urls:
            try:
                r = requests.post(haproxy_url, data=json.dumps(datas),
                            headers=self.headers, timeout=self._timeout)
                if int(r.status_code) != 200:
                    return False
            except requests.exceptions.Timeout:
                return False
            except Exception:
                return False
        return True

    def change_instance_state(self, new_state, haproxy_backend, instances = []):
        """ Change the state(enable or disable) of an instance in Haproxy conf.

            :param  new_state: string (disableserver or enableserver).
            :param  haproxy_backend: string the name of the haproxy backend where the instance is define.
            :param  instances: a list of instances(IP or DNS) to enable or disable
            :return boolean (True if operation succeed on all Haproxy otherwise return False)
        """
        data = {'backend': haproxy_backend, 'action':
                new_state, 'data': [{'name': i} for i in instances]}
        return self.hapi_post_request(data)


    def set_deploy_mode(self, haproxy_backend, action=True):
        """ Enable or disable the deployment mode of Haproxy.

            :param  haproxy_backend: string the name of the Haproxy backend.
            :param  action: boolean True: all new add instance request will be add in the backend _new.
                                    False: all new add instance request will be add in the standard backend.
            :return boolean (True if operation succeed on all Haproxy otherwise return False)
        """
        data = {'backend': haproxy_backend, 'action':
                'deployment', 'data': {'status': action}}
        return self.hapipostrequest(data)

    def switch_backends(self, haproxy_backends=[]):
        """ Do a switch between two backends.

            :param  haproxy_backends: list of two backends to switch(If the list has only one element,
                                    a second will be add with the same name than the first with "_new").
            :return boolean (True if operation succeed on all Haproxy otherwise return False)
        """
        if len(haproxy_backends) == 1:
            haproxy_backends.append(str(haproxy_backends[0]) + '_new')
        data = {'backend': haproxy_backends[0], 'action': 'swserver',
                'data': [{'name': haproxy_backends[1]}]}
        return self.hapipostrequest(data)

    def remove_instance(self, haproxy_backend, instances = []):
        """ Remove the instance(s) from an Haproxy backend.

            :param  haproxy_backend: string the name of the Haproxy backend.
            :param  instances: list of instance IP or Name to remove.
            :return boolean (True if operation succeed on all Haproxy
                             otherwise return False)
        """
        data = {'backend': haproxy_backend, 'action':
                'rmserver', 'data': [{'name': i} for i in instances]}
        return self.hapipostrequest(data)

    def add_instance(self, haproxy_backend, instances = [], port = 80, options = ['check']):
        """ Add the instance(s) in an Haproxy backend.

            :param  haproxy_backend: string the name of the Haproxy backend.
            :param  instances: list of instance IP or Name to add.
            :param  port: string or int of the destination port of the instance(s).
            :param  option: list of options to add at the end of the instance configuration.(ex: check, inter 5000...).
            :return boolean (True if operation succeed on all Haproxy
                             otherwise return False)
        """
        data = {'backend': haproxy_backend, 'action':
                'addserver', 'data': [{'name': haproxy_backend + '-' + i.replace('.','-'),
                'ip': i, 'port': port, 'options': options} for i in instances]}
        return self.hapipostrequest(data)

if __name__ == '__main__':
    hapi = Haproxyapi(['52.67.8.92', '52.67.57.36'])
    instances_list = [u'10.10.10.250']
    print(hapi.change_instance_state('enableserver', 'webtracking', instances_list))

