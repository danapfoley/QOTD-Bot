from time import time, sleep
from slackclient import SlackClient


class WellBehavedSlackClient(SlackClient):
    '''Slack client with rate limit'''

    def __init__(self, token, proxies=None, ratelimit=1.0):
        super().__init__(token, proxies)
        self.ratelimit = ratelimit
        self.last_invoked = time() - ratelimit

    def api_call(self, method, timeout=None, **kwargs):
        while True:
            now = time()
            if (now - self.last_invoked) >= self.ratelimit:
                try:
                    result = super().api_call(method, timeout=timeout, **kwargs)
                except:
                    print("Connection Error. Retrying in 3 seconds...")
                    sleep(3)
                    continue
                self.last_invoked = time()
                return result
            else:
                sleep(self.ratelimit - (now - self.last_invoked))
