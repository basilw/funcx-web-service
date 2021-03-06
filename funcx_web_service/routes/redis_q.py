import redis
import queue
import json

from funcx_web_service.models.tasks import TaskState, Task


class NotConnected(Exception):
    """ Queue is not connected/active
    """
    def __init__(self, queue):
        self.queue = queue

    def __repr__(self):
        return "Queue {} is not connected. Cannot execute queue operations".format(self.queue)


class RedisQueue(object):
    """ A basic redis queue

    The queue only connects when the `connect` method is called to avoid
    issues with passing an object across processes.

    Parameters
    ----------
    hostname : str
       Hostname of the redis server

    port : int
       Port at which the redis server can be reached. Default: 6379

    """

    def __init__(self, prefix, hostname, port=6379):
        """ Initialize
        """
        self.hostname = hostname
        self.port = port
        self.redis_client = None
        self.prefix = prefix

    def connect(self):
        """ Connects to the Redis server
        """
        try:
            if not self.redis_client:
                self.redis_client = redis.StrictRedis(host=self.hostname, port=self.port, decode_responses=True)
        except redis.exceptions.ConnectionError:
            print("ConnectionError while trying to connect to Redis@{}:{}".format(self.hostname,
                                                                                  self.port))

            raise

    '''
    def get(self, endpoint_id, timeout=1):
        """ Get an item from the redis queue

        Parameters
        ----------
        timeout : int
           Timeout for the blocking get in seconds
        """
        try:
            x = self.redis_client.blpop(f'{self.prefix}_{endpoint_id}_list', timeout=timeout)
            if not x:
                raise queue.Empty

            task_list, task_id = x
            jtask_info = self.redis_client.get(f'{self.prefix}_{endpoint_id}:{task_id}')
            task_info = json.loads(jtask_info)
        except queue.Empty:
            raise

        except AttributeError:
            raise NotConnected(self)

        except redis.exceptions.ConnectionError:
            print(f"ConnectionError while trying to connect to Redis@{self.hostname}:{self.port}")
            raise

        return task_id, task_info
    '''

    def get(self, kind, timeout=1):
        """ Get an item from the redis queue

        Parameters
        ----------
        kind : str
           Required. The kind of item to fetch from the DB

        timeout : int
           Timeout for the blocking get in seconds
        """
        try:
            x = self.redis_client.blpop(f'{self.prefix}_list', timeout=timeout)
            if not x:
                raise queue.Empty

            task_list, task_id = x
            jtask_info = self.redis_client.hget(f'task_{task_id}', kind)
            task_info = json.loads(jtask_info)
        except queue.Empty:
            raise

        except AttributeError:
            raise NotConnected(self)

        except redis.exceptions.ConnectionError:
            print(f"ConnectionError while trying to connect to Redis@{self.hostname}:{self.port}")
            raise

        return task_id, task_info

    '''
    def put(self, endpoint_id, key, payload):
        """ Put's the key:payload into a dict and pushes the key onto a queue
        Parameters
        ----------
        endpoint_id : str
            Target endpoint id

        key : str
            The task_id to be pushed

        payload : dict
            Dict of task information to be stored
        """
        try:
            self.redis_client.set(f'{self.prefix}_{endpoint_id}:{key}', json.dumps(payload))
            self.redis_client.rpush(f'{self.prefix}_{endpoint_id}_list', key)
        except AttributeError:
            raise NotConnected(self)
        except redis.exceptions.ConnectionError:
            print("ConnectionError while trying to connect to Redis@{}:{}".format(self.hostname,
                                                                                  self.port))
            raise
    '''

    def put(self, task_id, kind, payload):
        """ Put's the task_id:payload into a dict and pushes the task_id onto a queue
        Parameters
        ----------
        task_id : str
            The task_id to be pushed

        kind : str
            The type of payload

        payload : dict
            Dict of task information to be stored
        """
        try:
            self.redis_client.hset(f'task_{task_id}', kind, json.dumps(payload))
            self.redis_client.rpush(f'{self.prefix}_list', task_id)
        except AttributeError:
            raise NotConnected(self)
        except redis.exceptions.ConnectionError:
            print("ConnectionError while trying to connect to Redis@{}:{}".format(self.hostname,
                                                                                  self.port))
            raise

    @property
    def is_connected(self):
        return self.redis_client is not None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "<RedisQueue at {}:{}#{}".format(self.hostname, self.port, self.prefix)


class EndpointQueue(RedisQueue):
    """Encapsulates functionality required for placing tasks on Queue for an Endpoint in Redis"""
    def __init__(self, endpoint: str, hostname: str, port: int = 6379):
        super(EndpointQueue, self).__init__(f"task_{endpoint}", hostname, port=port)
        self.queue_name = f'{self.prefix}_list'
        self.endpoint = endpoint

    def enqueue(self, task: Task):
        # want to track more data so the task knows what endpoint queue it is living in
        # as well as whether it is currently running.  This is to distinguish the queued
        # from the running TaskState
        task.endpoint = self.endpoint
        task.status = TaskState.WAITING_FOR_EP
        self.redis_client.rpush(self.queue_name, task.task_id)

    def dequeue(self, timeout=1) -> Task:
        """Blocking dequeue for timeout in seconds"""
        # blpop returns a tuple of the list name (in case of popping across > 1 list) and the element
        res = self.redis_client.blpop(self.queue_name, timeout=timeout)
        if not res:
            raise queue.Empty

        # we only query 1 list, so we can ignore the list name
        _, task_id = res
        return Task.from_id(self.redis_client, task_id)


def test():
    rq = RedisQueue('task', '127.0.0.1')
    rq.connect()
    rq.put("01", {'a': 1, 'b': 2})
    res = rq.get(timeout=1)
    print("Result : ", res)


if __name__ == '__main__':
    test()
