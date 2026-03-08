import time

class Example:
    def __init__(self, config):
        pass

    async def process_text(
        self,
        request_id,
        text
    ):
        metrics = {
            'lowercase_time': 0.0
        }
        
        time_start = time.time()
        text = text.lower()
        metrics["lowercase_time"] += time.time() - time_start
        
        return {
            'text': text
        }, metrics