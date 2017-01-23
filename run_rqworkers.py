from multiprocessing import Process, active_children
from setproctitle import setproctitle
from time import sleep
import signal
import sys
import traceback

from redis import Redis
from rq import Queue, Worker

from pymongo import MongoClient

import logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

from settings import MONGO_DBNAME, MONGO_HOST, MONGO_PORT, REDIS_HOST

from ghost_tools import config, get_rq_name_from_app, get_app_from_rq_name, get_app_colored_env

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
    ghost_redis_connection = Redis(host=REDIS_HOST)
    ghost_rq_queues = {}
    ghost_rq_workers = {}

    # Register signal handler to terminate workers properly even when process is managed by supervisord
    def signal_handler(signal, frame):
        logging.info("received signal {}, terminating...".format(signal))

        sleep(1)
        for rqworker_name, rqworker in ghost_rq_workers.items():
            process = rqworker
            if process.is_alive():
                logging.info("terminating an rqworker: {}...".format(rqworker_name))
                rqworker.terminate()
                rqworker.join(1000)
            logging.info("rqworker terminated: {}".format(rqworker_name))

        sys.exit(0)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGQUIT, signal_handler)

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
                logging.debug("found an active rqworker: {}".format(rqworker_name))
                if not ghost_rq_workers.has_key(rqworker_name):
                    raise Exception("an active worker does not match a child process: {}".format(rqworker_name))

            # Verify that child processes match active workers
            for rqworker_name, rqworker in ghost_rq_workers.items():
                logging.debug("found a child process: {}".format(rqworker_name))
                if not ghost_rq_workers.has_key(rqworker_name):
                    raise Exception("a child process does not match an active rqworker: {}".format(rqworker_name))
                if not rqworker.is_alive():
                    raise Exception("a child process is not alive: {}".format(rqworker_name))

            # Get existing apps from MongoDB
            apps = [app for app in apps_db.find()]

            # Check that each app has an active worker
            for app in apps:
                rqworker_name = get_rq_name_from_app(app)
                if not ghost_rq_workers.has_key(rqworker_name):
                    create_rq_queue_and_worker(rqworker_name, ghost_rq_queues, ghost_rq_workers, ghost_redis_connection)

            # Check that each worker corresponds to an existing app
            for rqworker_name, rqworker in ghost_rq_workers.items():
                found = False
                rqworker_app = get_app_from_rq_name(rqworker_name)

                if rqworker_app['env'] != '*' and rqworker_app['role'] != '*':
                    for app in apps:
                        env = get_app_colored_env(app)
                        if env == rqworker_app['env'] and app['name'] == rqworker_app['name'] and app['role'] == rqworker_app['role']:
                            found = True
                    if not found:
                        delete_rq_queue_and_worker(rqworker_name, ghost_rq_queues, ghost_rq_workers)

        except:
            logging.error("an exception occurred: {}".format(sys.exc_value))
            traceback.print_exc()
        finally:
            # Invoke active_children() in order to avoid zombie processes
            active_children()

        # Short pause 
        sleep(60)


if __name__ == '__main__':
    manage_rq_workers()
