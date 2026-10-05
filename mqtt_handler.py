import asyncio
import json
import logging
import uuid
import aiomqtt

from database_manager import ManageSpaces as SpaceManager

MQTT_HOST = "mqtt.premavel.com.ng"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "jlaLtx8T2mzYwRffvWVj1Rp6"

SUBSCRIBE_TOPICS = [
  "Iviehub/notification",
  "Ivie/hub/device/status",
]

publish_queue = asyncio.Queue(maxsize=1000)

client = None
connected = asyncio.Event()

processed_message_ids = set()

async def message_handler(message):
  topic = str(message.topic)

  try:
    payload = message.payload.decode("utf-8")
  except (AttributeError, UnicodeDecodeError):
    payload = str(message.payload)

  try:
    msg = json.loads(payload)
  except (json.JSONDecodeError, TypeError):
    msg = payload


  print(f"Received on {topic}: {msg}")

  message_id = None

  if isinstance(msg, dict):
    message_id = msg.get("message_id")

  if message_id and message_id in processed_message_ids:
    print(
      f"Ignoring duplicate message: {message_id}"
    )
    return
  processed_message_ids.add(message_id)

  if topic.startswith("Iviehub/"):
    if topic == "Iviehub/register":
      username = msg.get("username")
      device_id = msg.get("device").get("device_id")
      response = await SpaceManager.register_device(msg)
      await publish(
        f"{device_id}/{username}",
        response
      )

    elif topic == "Iviehub/device":
      # await SpaceManager.notifier(msg)
      print(msg)

  elif topic.startswith("Ivie/"):
    pass

async def mqtt_listener():
  global client

  while True:
    try:
      async with aiomqtt.Client(
        hostname=MQTT_HOST,
        port=MQTT_PORT,
        identifier=MQTT_CLIENT_ID,
      ) as mqtt:
        
        client = mqtt

        for topic in SUBSCRIBE_TOPICS:
          await mqtt.subscribe(topic)

        connected.set()

        print("MQTT connected and subscribed.")

        async for message in mqtt.messages:
          try:
            await message_handler(message)
          except Exception:
            logging.exception(
              "Error handling MQTT message"
            )
    except aiomqtt.MqttError:
      logging.exception(
        "MQTT connection lost or failed"
      )
    finally:
      connected.clear()
      client = None

    print("Reconnecting to MQTT in 5 seconds...")
    await asyncio.sleep(5)

async def mqtt_publisher():
  while True:
    topic, payload, qos, retain = (await publish_queue.get())
    while True:
      try:
        await connected.wait()
        mqtt = client

        if mqtt is None:
          continue

        await mqtt.publish(
          topic,
          payload,
          qos=qos,
          retain=retain,
        )
        publish_queue.task_done()

        print(f"MQTT published: {topic}")
        break
      except aiomqtt.MqttError:
        connected.clear()
        logging.exception(
          "MQTT publish failed. Waiting for reconnect..."
        )
        await connected.wait()

async def publish(topic, payload, qos=0, retain=False):

  message_id = str(uuid.uuid4())

  if isinstance(payload, dict):
    payload = payload.copy()
    payload["message_id"] = message_id

  elif isinstance(payload, list):
    payload = json.dumps(payload)

  elif not isinstance(payload, str):
    payload = str(payload)

  await publish_queue.put(
    (
      topic,
      payload,
      qos,
      retain,
    )
  )
  return message_id

async def start_mqtt():
  asyncio.create_task(
    mqtt_listener()
  )

  asyncio.create_task(
    mqtt_publisher()
  )

  await connected.wait()