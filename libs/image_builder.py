import time
import os
import io

from ghost_log import log

from libs.blue_green import get_blue_green_from_app

AMI_BASE_FMT = "ami.{env}.{region}.{role}.{name}.{color}"
AMI_FMT = AMI_BASE_FMT + "{date}"

class ImageBuilder:
    def __init__(self, app, job, db, log_file, config):

        self._app = app
        self._job = job
        self._db = db
        self._log_file = log_file
        self._config = config

        blue_green, self._color = get_blue_green_from_app(self._app)
        self._ami_name = AMI_FMT.format(env=self._app['env'], region=self._app['region'],
                                                              role=self._app['role'],
                                                              name=self._app['name'],
                                                              date=time.strftime("%Y%m%d-%H%M%S"),
                                                              color='.%s' % self._color if self._color else '')

    def _format_salt_top_from_app_features(self):
        """ Generates the formula dictionnary object with all required features
        >>> class worker:
        ...     app = { \
                    'name': 'AppName', 'env': 'prod', 'role': 'webfront', 'region': 'eu-west-1',\
                    'features': [{'name': 'pkg', 'version': 'git_vim'}, {'name': 'pkg', 'version': 'package=lsof'}, {'name': 'pkg', 'version': 'package=curl'}]\
                 }
        ...     job = None
        ...     log_file = None
        ...     _config = None
        ...     _db = None
        >>> Buildimage(worker=worker())._format_salt_top_from_app_features()
        ['pkg']
        """
        top = []
        for i in self._app['features']:
            if re.search('^(php|php5)-(.*)',i['name']):
                continue
            if re.search('^zabbix-(.*)',i['name']):
                continue
            if re.search('^gem-(.*)',i['name']):
                continue
            if not i['name'].encode('utf-8') in top:
                top.append(i['name'].encode('utf-8'))
        return top

    def _format_salt_pillar_from_app_features(self):
        """ Generates the pillar dictionnary object with all required features and their options
        >>> class worker:
        ...     app = { \
                    'name': 'AppName', 'env': 'prod', 'role': 'webfront', 'region': 'eu-west-1',\
                    'features': [{'name': 'pkg', 'version': 'git_vim'}, {'name': 'pkg', 'version': 'package=lsof'}, {'name': 'pkg', 'version': 'package=curl'}]\
                }
        ...     job = None
        ...     log_file = None
        ...     _config = None
        ...     _db = None
        >>> import pprint
        >>> pprint.pprint(Buildimage(worker=worker())._format_salt_pillar_from_app_features().items())
        [('pkg', {'package': ['lsof', 'curl'], 'version': 'git_vim'})]
        """
        pillar = {}
        for ft in self._app['features']:
            values = ft.get('version', '').split('=', 1) # Split only one time
            feature_name = ft['name'].encode('utf-8')
            if not feature_name in pillar:
                pillar[feature_name] = {}
            if len(values) == 2:
                ft_param_key = values[0].encode('utf-8')
                ft_param_val = values[1].encode('utf-8')
                if not ft_param_key in pillar[feature_name]:
                    pillar[feature_name][ft_param_key] = []
                pillar[feature_name][ft_param_key].append(ft_param_val)
            else:
                pillar[feature_name]['version'] = ft.get('version', '').encode('utf-8')
        return pillar

    def _generate_buildimage_hook(self, hook_name):
        """ Generates a buildimage hook script
        >>> from StringIO import StringIO
        >>> from ghost_tools import b64encode_utf8
        >>> class worker:
        ...     app = { \
                    'name': 'AppName', 'env': 'prod', 'role': 'webfront', 'region': 'eu-west-1',\
                    'lifecycle_hooks': {'pre_buildimage': u'', 'post_buildimage': b64encode_utf8(u'echo Custom post-buildimage script')}\
                 }
        ...     job = None
        ...     log_file = StringIO()
        ...     _config = None
        ...     _db = None

        >>> Buildimage(worker=worker())._generate_buildimage_hook('pre_buildimage')
        '/ghost/AppName/prod/webfront/hook-pre_buildimage'
        >>> with io.open('/ghost/AppName/prod/webfront/hook-pre_buildimage', encoding='utf-8') as f:
        ...   f.read()
        u'echo No pre_buildimage script'

        >>> Buildimage(worker=worker())._generate_buildimage_hook('post_buildimage')
        '/ghost/AppName/prod/webfront/hook-post_buildimage'
        >>> with io.open('/ghost/AppName/prod/webfront/hook-post_buildimage', encoding='utf-8') as f:
        ...   f.read()
        u'echo Custom post-buildimage script'
        """
        log("Create '%s' script for Packer" % hook_name, self._log_file)
        lfc_hooks = self._app.get('lifecycle_hooks', None)
        if not lfc_hooks or not lfc_hooks.get(hook_name, None):
            hook_source = u"echo No {hook_name} script".format(hook_name=hook_name)
        else:
            hook_source = b64decode_utf8(self._app['lifecycle_hooks'][hook_name])
        app_path = "/ghost/{name}/{env}/{role}".format(name=self._app['name'], env=self._app['env'], role=self._app['role'])
        if not os.path.exists(app_path):
            os.makedirs(app_path)
        hook_file_path = "{app_path}/hook-{hook_name}".format(app_path=app_path, hook_name=hook_name)
        with io.open(hook_file_path, mode='w', encoding='utf-8') as f:
            f.write(hook_source)
        return hook_file_path

    def _get_buildimage_hooks(self):
        hooks = {}
        hooks['pre_buildimage'] = self._generate_buildimage_hook('pre_buildimage')
        hooks['post_buildimage'] = self._generate_buildimage_hook('post_buildimage')
        return hooks
