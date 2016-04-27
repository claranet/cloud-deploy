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
import requests
import json
import itertools

from ghost_log import log

class Haproxyapi:
    """A lightweight class for interraction with Hapi, an API for HAproxy"""

    def __init__(self, haproxy_ips, log_file, hapi_port = '5001', timeout = 3, retry = 3):
        """ Initialize the variable to communicate with Hapi an Haproxy API.

            :param  haproxy_ips: list of Haproxy IPs.
            :param  hapi_port: string or int of the Hapi port.
            :param  timeout: int the default timeout for each request on the API.
            :param  retry: int maximum retry for each request on the API.
            :param  log_file  string  The log file.
        """
        self.headers = {'content-type': 'application/json'}
        self.log_file = log_file
        self._urls = ['http://{0}:{1}/haproxy' .format(ip, str(hapi_port)) for ip in haproxy_ips]
        self._timeout = int(timeout)
        requests.adapters.DEFAULT_RETRIES = int(retry)

    def get_haproxy_urls(self):
        """ Returns a list of Haproxy URls

            :return list of Haproxy URLs
        """
        return self._urls

    def conf_cleaner(self, datas):
        """ Return a conf dict without any space \t \n.

            :param datas  dict of an Haproxy configuration
            :return dict.
        """
        clean_conf = {}
        for k, v in datas.items():
            new_infos = []
            for infos in v:
                new_infos.append({''.join(str(k).split()):''.join(str(v).split()) for k,v in infos.items()})
            clean_conf[k] = new_infos
        return clean_conf

    def check_haproxy_conf(self, haproxy_conf = []):
        """ Do the difference between Haproxy's configuration. Compare only if each
            Haproxy conf have the same running instances.

            :param   haproxy_conf: list of Haproxy configurations(backend with instances IPs).
            :return  boolean (True if conf are equal otherwise False)
        """
        haproxy_conf = [sorted([i['ip'] for i in self.conf_cleaner(i).values()[0] if i['status'] == 'up']) for i in haproxy_conf]
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
        for backend in self.hapi_get_request('show', haproxy_url):
            if expand:
                haproxy_conf[backend] = self.hapi_get_request('show={0}' .format(backend), haproxy_url)
            else:
                haproxy_conf[backend] = [ip['ip'].split(':')[0] for ip in self.hapi_get_request('show={0}' .format(backend), haproxy_url)]
        return haproxy_conf

    def hapi_get_request(self, datas, haproxy_url):
        """ Perform a Get request on Haproxy APIs.

            :param   datas: String: The get parameters.
            :param   haproxy_urls:  string: The Haproxy URL on which to perform the request.
            :return  a list: The values of the get request answer.
        """
        try:
            rez = requests.get(haproxy_url + '?' + datas)
            if int(rez.status_code) == 200:
                return rez.json().values()[0]
        except requests.exceptions.ConnectionError:
            log("Connection Error on the Haproxy: {0}" .format(haproxy_url), self.log_file)
        except requests.exceptions.Timeout:
            log("Connection Timeout on the Haproxy: {0}" .format(haproxy_url), self.log_file)
        except Exception as e:
            log("Error during post_request operation: {0}" .format(str(e)), self.log_file)
        return []

    def hapi_post_request(self, datas, haproxy_url):
        """ Perform a Post request on Haproxy APIs.

            :param   datas: a dictionnary of the datas to send.
            :param   haproxy_urls:  string: The Haproxy URL on which to perform the request.
            :return  boolean (True if all requests succeed otherwise False).
        """
        try:
            r = requests.post(haproxy_url, data=json.dumps(datas),
                            headers=self.headers, timeout=self._timeout)
            if int(r.status_code) == 200:
                return True
        except requests.exceptions.ConnectionError:
            log("Connection Error on the Haproxy: {0}" .format(haproxy_url), self.log_file)
        except requests.exceptions.Timeout:
            log("Connection Timeout on the Haproxy: {0}" .format(haproxy_url), self.log_file)
        except Exception as e:
            log("Error during post_request operation: {0}" .format(str(e)), self.log_file)
        return False

    def change_instance_state(self, new_state, haproxy_backend, instances = []):
        """ Change the state(enable or disable) of an instance in Haproxy conf.

            :param  new_state: string (disableserver or enableserver).
            :param  haproxy_backend: string the name of the haproxy backend where the instance is define.
            :param  instances: a list of instances(IP or DNS) to enable or disable
            :return boolean (True if operation succeed on all Haproxy otherwise return False)
        """
        data = {'backend': haproxy_backend, 'action':
                new_state, 'data': [{'name': i} for i in instances]}
        for ha_url in self._urls:
            if not self.hapi_post_request(data, ha_url):
                return False
        return True


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
