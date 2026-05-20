# backend/tests/mocks/redis_mock.py
from unittest.mock import MagicMock

class MockRedisClient:
    """Мок Redis клиента для тестов."""
    
    def __init__(self):
        self._data = {}
    
    def get(self, key):
        return self._data.get(key)
    
    def setex(self, key, time, value):
        self._data[key] = value
        return True
    
    def incr(self, key):
        self._data[key] = str(int(self._data.get(key, '0')) + 1)
        return self._data[key]
    
    def expire(self, key, time):
        return True
    
    def ttl(self, key):
        return 900
    
    def pipeline(self):
        return MockPipeline(self)


class MockPipeline:
    def __init__(self, client):
        self.client = client
        self.commands = []
    
    def incr(self, key):
        self.commands.append(('incr', key))
        return self
    
    def expire(self, key, time):
        self.commands.append(('expire', key, time))
        return self
    
    def execute(self):
        results = []
        for cmd in self.commands:
            if cmd[0] == 'incr':
                results.append(int(self.client.incr(cmd[1])))
            elif cmd[0] == 'expire':
                results.append(self.client.expire(cmd[1], cmd[2]))
        self.commands = []
        return results


def get_mock_redis():
    return MockRedisClient()