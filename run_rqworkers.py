from multiprocessing import Process, active_children
from setproctitle import setproctitle
from time import sleep
import sys
import traceback

from redis import Redis
from rq import Queue, Worker

from pymongo import MongoClient

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

from settings import MONGO_DBNAME, MONGO_HOST, MONGO_PORT

def get_rq_name_from_app(app):
    """
    Returns an RQ name for a given ghost app

    >>> get_rq_name_from_app({'env': 'prod', 'name': 'App1', 'role': 'webfront'})
    'prod:App1:webfront'
    """
    return '{env}:{name}:{role}'.format(env=app['env'], name=app['name'], role=app['role'])

def get_app_from_rq_name(name):
    """
    Returns an app's env, name, role for a given RQ name

    >>> sorted(get_app_from_rq_name('prod:App1:webfront').items())
    [('env', 'prod'), ('name', 'App1'), ('role', 'webfront')]
    """
    parts = name.split(':')
    return {'env': parts[0], 'name': parts[1], 'role': parts[2]}

def create_rq_queue_and_worker(rqworker_name, ghost_rq_queues, ghost_rq_workers, ghost_redis_connection):
    ghost_rq_queues[rqworker_name] = Queue(name=rqworker_name, connection=ghost_redis_connection, default_timeout=3600)
    worker = Worker(name=rqworker_name, queues=[ghost_rq_queues[rqworker_name]], connection=ghost_redis_connection)

    def start_worker(worker, rqworker_name):
        setproctitle('rqworker-{}'.format(rqworker_name))
        worker.work()

    # Fork a dedicated RQ worker process
    ghost_rq_workers[rqworker_name] = Process(target=start_worker, args=[worker, rqworker_name])
    ghost_rq_workers[rqworker_name].start()
    logging.info('Started rqworker {0}'.format(rqworker_name))

def delete_rq_queue_and_worker(rqworker_name, ghost_rq_queues, ghost_rq_workers):
    queue = ghost_rq_queues[rqworker_name]
    queue.empty()
    # TODO: delete queue in redis
    # ghost.ghost_redis_connection.delete(queue.key)
    del ghost_rq_queues[rqworker_name]

    # Terminate the RQ worker with a TERM signal to perform a warm shutdown
    ghost_rq_workers[rqworker_name].terminate()
    del ghost_rq_workers[rqworker_name]
    logging.info('Killed rqworker {0}'.format(rqworker_name))

def manage_rq_workers():
    ghost_redis_connection = Redis()
    ghost_rq_queues = {}
    ghost_rq_workers = {}

    apps_db = MongoClient(host=MONGO_HOST, port=MONGO_PORT)[MONGO_DBNAME]['apps']

    # Manage RQ workers for existing apps, terminating RQ workers with no
    while True:
        try:
            logging.info("refreshing workers")

            # Get active workers from Redis' point of view
            active_rqworkers = Worker.all(connection=ghost_redis_connection)

            # Verify that active workers match child processes
            for rqworker in active_rqworkers:
                rqworker_name = rqworker.name
                logging.debug("found an active worker: {}".format(rqworker_name))
                if not ghost_rq_workers.has_key(rqworker_name):
                    logging.error("ERROR: an active worker does not match a child process: {}".format(rqworker_name))
                    sys.exit(-1)

            # Verify that child processes match active workers
            for rqworker in ghost_rq_workers.items():
                rqworker_name = rqworker[0]
                logging.debug("found a child process: {}".format(rqworker_name))
                if not ghost_rq_workers.has_key(rqworker_name):
                    logging.error("a child process does not match an active worker: {}".format(rqworker_name))
                    sys.exit(-2)
                if not rqworker[1].is_alive():
                    logging.warn("a child process is not alive: {}".format(rqworker_name))
                    sys.exit(-3)

            # Get existing apps from MongoDB
            apps = [app for app in apps_db.find()]

            # Check that each app has an active worker
            for app in apps:
                rqworker_name = get_rq_name_from_app(app)
                if not ghost_rq_workers.has_key(rqworker_name):
                    create_rq_queue_and_worker(rqworker_name, ghost_rq_queues, ghost_rq_workers, ghost_redis_connection)

            # Check that each worker corresponds to an existing app
            for rqworker in ghost_rq_workers.items():
                found = False
                rqworker_name = rqworker[0]
                rqworker_app = get_app_from_rq_name(rqworker_name)
                for app in apps:
                    if app['env'] == rqworker_app['env'] and app['name'] == rqworker_app['name'] and app['role'] == rqworker_app['role']:
                        found = True
                if not found:
                    delete_rq_queue_and_worker(rqworker_name, ghost_rq_queues, ghost_rq_workers)

        except:
            logging.error("an exception occurred {}".format(sys.exc_value))
            traceback.print_exc()
        finally:
            # Invoke active_children() in order to avoid zombie processes
            active_children()

        # Short pause 
        sleep(60)


if __name__ == '__main__':
    manage_rq_workers()
