from datetime import datetime
import asyncio
import time

class scheduler:
  def __init__(self, now, start_at=None, end_at=None):
    self.start_timestamp = int(
      datetime.fromisoformat(start_at or now).timestamp()
    )
    self.end_timestamp = int(
      datetime.fromisoformat(end_at or now).timestamp()
    )

  async def Start_at(self):
    # Wait until access starts
    current_time = int(time.time())

    if current_time < self.start_timestamp:
      await asyncio.sleep(
        self.start_timestamp - current_time
      )

  async def End_at(self):
    # Wait until access expires
    current_time = int(time.time())

    if current_time < self.end_timestamp:
      await asyncio.sleep(
        self.end_timestamp - current_time
      )

# asyncio.run(access_control())