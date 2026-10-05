import logging
import os
import json
from dotenv import load_dotenv
import asyncio
import base64
import mimetypes
import random
from telebot.async_telebot import AsyncTeleBot
import time
from telebot.types import (
	InlineKeyboardButton,
	InlineKeyboardMarkup,
	KeyboardButton,
	ReplyKeyboardMarkup,
	ReplyKeyboardRemove,
	InputMediaPhoto, 
	InputMediaVideo
)
from telebot.apihelper import ApiTelegramException
from geopy.geocoders import Nominatim
from bs4 import BeautifulSoup
import pathlib
from pathlib import Path
import multiprocessing
from timezonefinder import TimezoneFinder

LOG_FILE = Path(__file__).resolve().parent / "logs/system.log"
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
    ]
)

logger = logging.getLogger(__name__)

from orchestrators import ORCHESTRATOR
from video_orchestrator import video_orchestrator
from database_manager import (
	DatabaseArchitecture, 
	Tables,
	Authenticator,
	ManageUsers
)
from VoiceOrchestrator import STT, TTS
import mqtt_handler

geolocator = Nominatim(user_agent="telegram_bot_locator")
timezone_finder = TimezoneFinder()

load_dotenv()
BOT_TOKEN = os.getenv("WILL_BOT")
bot = AsyncTeleBot(BOT_TOKEN)

# from telegram.constants import ChatAction
# ChatAction.TYPING

# ChatAction.UPLOAD_PHOTO
# ChatAction.RECORD_VIDEO
# ChatAction.UPLOAD_VIDEO

# ChatAction.RECORD_VOICE
# ChatAction.UPLOAD_VOICE

# ChatAction.UPLOAD_DOCUMENT

# ChatAction.CHOOSE_STICKER

# ChatAction.FIND_LOCATION

# ChatAction.RECORD_VIDEO_NOTE
# ChatAction.UPLOAD_VIDEO_NOTE

# Action String:

# typing

# upload_photo
# record_video
# upload_video

# record_voice
# upload_voice

# upload_document

# choose_sticker

# find_location

# record_video_note
# upload_video_note

msg_ids = {}
status_msg = [
	"<i>Pretending to think...</i>",
	"<i>Calculating how much I care...</i>",
	"<i>Thinking... allegedly.</i>",
	"<i>Calculating my next move...</i>",
	"<i>Trying to impress you...</i>",
	"<i>Looking busy...</i>",
	"<i>Consulting the oracle...</i>",
	"<i>Doing my thing...</i>",
	"<i>Give me a moment, genius at work...</i>",
	"<i>Processing</i>"
]

@bot.message_handler(commands=['start'])
async def Assistant(message):
	user_id = message.from_user.id
	chat_id = message.chat.id
	message_id = message.message_id

	first_name = message.from_user.first_name
	last_name = message.from_user.last_name or ""
	full_name = f"{first_name} {last_name}".strip()

	auth = Authenticator(user_id)

	if await auth.user_exists() and await auth.chat_exists():

		await ManageUsers.save_chat(
			user_id=user_id,
			message_id=message_id,
			message_type="UI",
			role="user",
			content=f"{full_name} just logged back in.",
			
		)

		status = await bot.send_message(
			chat_id=chat_id, 
			text=f"<i>Processing...</i>", 
			parse_mode="HTML"
		)

		await bot.delete_message(
			chat_id=chat_id,
			message_id=message_id
		)
		
		await bot.send_chat_action(
			chat_id=chat_id,
			action='typing'
		)
		await orchestrate_response(chat_id, status.message_id)
	else:
		text = (
			"<b>📜 Privacy Policy & Consent</b>\n\n"
			"👋 Welcome to <b>Will</b>!\n\n"
			"Before we get started, please review and accept our <b>Privacy Policy</b>.\n\n"
			"Use the buttons below to either <b>Accept</b> or <b>Decline</b>.\n\n"
			"<i>Acceptance is required to create your account and access all of Will's features.</i>"
		)

		accept = InlineKeyboardButton(text='Accept', callback_data='policy_accept')
		decline = InlineKeyboardButton(text='Decline', callback_data='policy_decline')

		policy_keyboard = InlineKeyboardMarkup()
		policy_keyboard.row(accept, decline)

		await bot.send_message(
			chat_id,
			text,
			reply_markup=policy_keyboard,
			parse_mode="HTML"
		)

		await bot.delete_message(
			chat_id=chat_id,
			message_id=message_id
		)
				

@bot.callback_query_handler(func=lambda call: call.data == "policy_accept")
async def handle_accept(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    first_name = call.from_user.first_name
    last_name = call.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    User_Manager = ManageUsers(user_id)

    auth = Authenticator(user_id)
    if not await auth.user_exists():
        await User_Manager.register_user(full_name)

    memory = {
		'create': {
			'user_name': full_name
		}
    }
    await User_Manager.mamage_memory(memory)

    text = (
		"To continue your setup, please share your <b>location 📍</b> and "
		"<b>contact details 📱</b> using the buttons below.\n\n"
		"<i>As explained in our Privacy Policy, this information is required "
		"to verify your account, personalize your experience, enable location-based "
		"features, and keep your account secure.</i>"
	)

    reply_keyboard = ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True
    )

    location_btn = KeyboardButton(
        "📍 Share location",
        request_location=True
    )

    contact_btn = KeyboardButton(
        "📱 Share contact",
        request_contact=True
    )

    reply_keyboard.add(contact_btn, location_btn)

    bot_msg = await bot.send_message(
		chat_id,
		text,
		reply_markup=reply_keyboard,
		parse_mode="HTML"
	)

    await bot.delete_message(
		chat_id=chat_id,
		message_id=message_id
	)

    msg_ids.setdefault(user_id, []).append(bot_msg.message_id)

@bot.message_handler(content_types=['location', 'contact'])
async def handle_location(message):

	user_id = message.from_user.id
	chat_id = message.chat.id
	message_id = message.message_id
	error_msg = None

	msg_ids.setdefault(user_id, []).append(message_id)

	User_Manager = ManageUsers(user_id)

	if message.location: 
		await bot.send_chat_action(
			chat_id=chat_id,
			action='find_location'
		)

		loc = message.location
		
		try:
			Coordinates = geolocator.reverse((loc.latitude, loc.longitude), language='en')
			timezone = timezone_finder.timezone_at(lat=loc.latitude, lng=loc.longitude)
			await User_Manager.save_time_zone(timezone)
			if Coordinates:
				address = Coordinates.raw.get('address', {})
				postal_code = address.get('postcode')
				city = address.get('city') or address.get('town') or address.get('village')
				state = address.get('state')
				country = address.get('country')
				location = f"{city}, {state}, {country}"
				if postal_code:
					location += f"\nPostal Code: {postal_code}"

				await User_Manager.save_location(f"{location}\nlatitude: {loc.latitude}, \nlongitude: {loc.longitude}")
				
				memory = {
					'create': {
						'location': location, 
						"home_coordinates": {
						"latitude": loc.latitude,
						"longitude": loc.longitude
						}
					}
				}
				await User_Manager.mamage_memory(memory)
				
		except Exception:
			error_msg = (
				"📍 <b>Location Received</b>\n\n"
				"We received your location, but couldn't determine your address. 😓\n\n"
				"Please try sharing your location again."
			)
			
	elif message.contact:
		
		contact_info = message.contact
		contact = contact_info.phone_number
		await User_Manager.save_number(contact)

		memory = {
			'create': {
				'phone_number': contact
			}
		}
		await User_Manager.mamage_memory(memory)

	confirmation = await User_Manager.get_ph_loc()
	con_loc = "Contact" if message.contact else "Location"
	null_data = "Location" if con_loc == "Contact" else "Contact"
	text = error_msg or (
		f"✅ <b>{con_loc} Received</b>\n\n"
		f"Thanks! Your {con_loc.lower()} has been received. "
		f"Please share your {null_data.lower()} to continue."
	)
	if not confirmation[0] or not confirmation[-1]:

		reply_keyboard = ReplyKeyboardMarkup(
			resize_keyboard=True,
			one_time_keyboard=True
		)

		location_btn = KeyboardButton(
			"📍 Share location",
			request_location=True
		)

		contact_btn = KeyboardButton(
			"📱 Share contact",
			request_contact=True
		)

		button = contact_btn if not confirmation[0] else location_btn

		reply_keyboard.add(button)

		bot_msg = await bot.send_message(
			chat_id,
			text,
			parse_mode="HTML",
			reply_markup=reply_keyboard
		)

		msg_ids.setdefault(user_id, []).append(bot_msg.message_id)

	elif confirmation[0] and confirmation[-1]:

		bot_msg = await bot.send_message(
			chat_id,
			text[:-39],
			reply_markup=ReplyKeyboardRemove(),
			parse_mode="HTML"
		)

		msg_ids.setdefault(user_id, []).append(bot_msg.message_id)

		gender_text = (
			"Before we continue, please select your <b>gender</b>."
		)

		male = InlineKeyboardButton(text='Male', callback_data='male')
		female = InlineKeyboardButton(text='Female', callback_data='female')
	
		gender_keyboard = InlineKeyboardMarkup()
		gender_keyboard.row(male, female)
		
		await bot.send_message(
			chat_id,
			gender_text,
			reply_markup=gender_keyboard,
			parse_mode="HTML"
		)

@bot.callback_query_handler(func=lambda call: call.data in ("male", "female"))
async def handle_gender(call):
	user_id = call.from_user.id
	chat_id = call.message.chat.id
	message_id = call.message.message_id

	first_name = call.from_user.first_name
	last_name = call.from_user.last_name or ""
	full_name = f"{first_name} {last_name}".strip()

	gender = call.data

	await Tables.chat_table(user_id)
	User_Manager = ManageUsers(user_id)
	await User_Manager.save_gender(gender)
	memory = {
		"create": {
		"Gender": gender
		}
	}
	await User_Manager.mamage_memory(memory)

	text = (
		f"{full_name} just signed in for the first time. "
		"Greet the user and introduce yourself."
	)

	await User_Manager.save_chat(
		user_id=user_id,
		message_id=message_id,
		message_type='text',
		role="user",
		content=text,
	)

	await bot.edit_message_text(
		"<i>Processing...</i>",
		chat_id=chat_id,
		message_id=message_id,
		parse_mode="HTML"
	)

	await bot.delete_messages(
		chat_id,
		message_ids=msg_ids[user_id]
	)

	msg_ids.pop(user_id)
	
	await bot.send_chat_action(
		chat_id=chat_id,
		action='typing'
	)
	await orchestrate_response(chat_id, message_id)

@bot.callback_query_handler(func=lambda call: call.data == "policy_decline")
async def handle_reject(call):
	chat_id = call.message.chat.id
	message_id = call.message.message_id

	text = (
		"🚫 <b>Access Denied</b>\n\n"
		"You must accept our Privacy Policy and Consent Agreement to continue using the platform."
	)

	back = InlineKeyboardButton(text='Back', callback_data='back')

	back_keyboard = InlineKeyboardMarkup()
	back_keyboard.row(back)

	await bot.edit_message_text(
		text,
		chat_id=chat_id,
		message_id=message_id,
		parse_mode="HTML",
		reply_markup=back_keyboard
	)

@bot.callback_query_handler(func=lambda call: call.data == "back")
async def handle_reject(call):
	chat_id = call.message.chat.id
	message_id = call.message.message_id

	text = (
		"<b>📜 Privacy Policy & Consent</b>\n\n"
		"👋 Welcome to <b>Will</b>!\n\n"
		"Before we get started, please review and accept our <b>Privacy Policy</b>.\n\n"
		"Use the buttons below to either <b>Accept</b> or <b>Decline</b>.\n\n"
		"<i>Acceptance is required to create your account and access all of Will's features.</i>"
	)

	accept = InlineKeyboardButton(text='Accept', callback_data='policy_accept')
	decline = InlineKeyboardButton(text='Decline', callback_data='policy_decline')

	policy_keyboard = InlineKeyboardMarkup()
	policy_keyboard.row(accept, decline)

	await bot.edit_message_text(
		text,
		chat_id=chat_id,
		message_id=message_id,
		parse_mode="HTML",
		reply_markup=policy_keyboard
	)

async def AI_status(msg_type, chat_id):
	if msg_type == 'text':
		await bot.send_chat_action(
			chat_id=chat_id,
			action='typing'
		)
	elif msg_type in ["audio", "voice"]:
		await bot.send_chat_action(
			chat_id=chat_id,
			action='record_voice'
		)
	else:
		await bot.send_chat_action(
			chat_id=chat_id,
			action='record_video'
		)

async def orchestrate_response(chat_id, message_id, msg_type='text'):

	if msg_type in ['audio', 'voice']:
		await bot.edit_message_text(
			chat_id=chat_id,
			message_id=message_id,
			text=f"<i>Generating response...</i>",
			parse_mode="HTML"
		)
	elif msg_type == "video":
		await bot.edit_message_text(
			chat_id=chat_id,
			message_id=message_id,
			text=random.choice(status_msg),
			parse_mode="HTML"
		)

	await AI_status(msg_type, chat_id)

	response = ""
	first_stream = True
	last_stream = time.time()
	STREAM_INTERVAL = 0.5
	LLM = ORCHESTRATOR(chat_id)
	async for generated_text in LLM.orchestrator():
		if isinstance(generated_text, pathlib.PosixPath):
			with open(voice_note, "rb") as audio:
				await bot.send_audio(
					chat_id=chat_id,
					audio=audio
					# caption="🎵 Here's your audio."
				)
			return
		elif isinstance(generated_text, tuple):
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=response or "<i>Generating voice note...</i>",
				parse_mode="HTML"
			)

			await bot.send_chat_action(
				chat_id=chat_id,
				action='upload_voice'
			)

			msg = generated_text.get("voice_message")
			voice_id = generated_text.get("voice_id")
			
			voice_path = TTS(chat_id, voice_id, msg)
			voice_note = await voice_path.VoicePath()

			await bot.delete_message(chat_id, message_id)

			with open(voice_note, "rb") as voice:
				await bot.send_voice(
					chat_id=chat_id,
					voice=voice
					# caption="🎤 Here's your voice note."
				)
			return

		else:
			response = generated_text
			now = time.time()
			if first_stream or now - last_stream >= STREAM_INTERVAL or stream_response.endswith("</response>"):
				stream_response = BeautifulSoup(generated_text, "html.parser").get_text()
				try:
					await bot.edit_message_text(
						chat_id=chat_id,
						message_id=message_id,
						text=stream_response
					)
					last_stream, first_stream = now, False
				except Exception:
					logger.exception("Error during streaming")
	try:
		response.replace("</response>", "")
		if msg_type == 'text':
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=response,
				parse_mode="HTML"
			)

	except Exception:
		logger.exception("Response delivery failed")
		# response = strip_markdown(response)
		fallback_msg = BeautifulSoup(response, "html.parser").get_text()
		try:
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=fallback_msg
			)

		except Exception:
			logger.exception("Unexpected delivery error")
			fallback_msg = "⚠️ <b>An error occurred while sending Will's response.</b>"
			await bot.edit_message_text(
				chat_id, 
				message_id, 
				fallback_msg, 
				parse_mode="HTML"
			)

@bot.message_handler(func=lambda message: True)
async def assistant(message):
	user_id = message.from_user.id
	chat_id = message.chat.id
	message_id = message.message_id
	msg = message.text
	startup_bypass = await ManageUsers.save_chat(
		user_id=user_id, 
		message_id=message_id, 
		role="user", 
		content=msg
	)
	if startup_bypass:
		status = await bot.send_message(
			chat_id,
			startup_bypass,
			parse_mode="HTML"
		)
		msg_ids.setdefault(user_id, []).append(message_id)
		msg_ids.setdefault(user_id, []).append(status.message_id)
	else:
		status = await bot.send_message(
			chat_id=chat_id, 
			text="<i>Processing</i>", 
			parse_mode="HTML"
		)
		await bot.send_chat_action(
			chat_id=chat_id,
			action='typing'
		)
		await orchestrate_response(chat_id, status.message_id)

@bot.message_handler(content_types=['audio', 'voice'])
async def voice_messager(message):
	user_id = message.from_user.id
	chat_id = message.chat.id
	message_id = message.message_id

	if not await Authenticator(user_id).chat_exists():
		status = await bot.send_message(
			chat_id,
			"<b>⚠️ Unauthorized Access Attempt</b>\n\n"
			"Attempts to bypass or circumvent the onboarding process are <b>strictly prohibited</b>.\n\n"
			"Please complete the required onboarding steps to continue using the service.",
			parse_mode="HTML"
		)

		msg_ids.setdefault(user_id, []).append(message_id)
		msg_ids.setdefault(user_id, []).append(status.message_id)
		return

	status = await bot.send_message(
		chat_id=chat_id, 
		text=f"<i>Processing {'voice note' if message.voice else 'audio'}...</i>", 
		parse_mode="HTML"
	)

	await bot.send_chat_action(
		chat_id=chat_id,
		action='upload_voice'
	)

	user_dir = Path("audio_db") / str(user_id)
	user_dir.mkdir(parents=True, exist_ok=True)

	file = message.voice or message.audio

	file_info = await bot.get_file(file.file_id)
	downloaded_file = await bot.download_file(file_info.file_path)

	file = [
		int(f.stem.replace("voice_note", ""))
		for f in user_dir.glob("voice_note*.ogg")
	]
	fileNum = max(file, default=0) + 1

	audio_path = user_dir / f"voice_note{fileNum}.ogg"

	with open(audio_path, "wb") as f:
		f.write(downloaded_file)

	transcriber = STT(audio_path)
	transcribe = await transcriber.transcribe()

	processed_message = f"<backend_speech_to_text>{transcribe}</backend_speech_to_text>"

	await ManageUsers.save_chat(user_id, message_id, processed_message, "user", "audio")
	await orchestrate_response(chat_id, status.message_id, "voice" if message.voice else "audio")

async def get_folder(*parts) -> Path:
    path = Path("media_db").joinpath(*(str(part) for part in parts))
    path.mkdir(parents=True, exist_ok=True)
    return path

MAX_SIZE_MB = 20

async def save_file(folder: Path, file_id: str, ext: str):
    file_info = await bot.get_file(file_id)
    downloaded = await bot.download_file(file_info.file_path)

    file_path = folder / f"{file_id}.{ext}"
    with open(file_path, "wb") as f:
        f.write(downloaded)

    return file_path

# video_lock = multiprocessing.Lock()
video_semaphore = multiprocessing.Semaphore(1)
async def video_processor(user_id, content, message_id):
	try:
		await video_orchestrator(user_id, content)
	except Exception as e:
		logger.exception("Error while processing video")
		fallback_msg = "⚠️ <b>An error occurred while generating your response. Please try sending your message again.</b>"
		await bot.edit_message_text(
			user_id, 
			message_id, 
			fallback_msg, 
			parse_mode="HTML"
		)
	finally:
		video_semaphore.release()
	await orchestrate_response(user_id, message_id, "video")

def video_process_entry(user_id, content, message_id):
  asyncio.run(video_processor(user_id, content, message_id))

@bot.message_handler(content_types=['photo', 'video'])
async def media_handler(message):
	user_id = message.from_user.id
	message_id = message.message_id
	media_type = message.content_type
	group_id = message.media_group_id
	caption = message.caption

	text = "<i>Analyzing video, no panic...</i>" if media_type == "video" else "<i>Processing</i>"
	status = await bot.send_message(
		chat_id=user_id, 
		text=text, 
		parse_mode="HTML"
	)

	auth = Authenticator(user_id)

	if not await auth.chat_exists():
		status = await bot.send_message(
			user_id,
			"<b>⚠️ Unauthorized Access Attempt</b>\n\n"
			"Attempts to bypass or circumvent the onboarding process are <b>strictly prohibited</b>.\n\n"
			"Please complete the required onboarding steps to continue using the service.",
			parse_mode="HTML"
		)
		msg_ids.setdefault(user_id, []).append(message_id)
		msg_ids.setdefault(user_id, []).append(status.message_id)
		return
	
	if group_id:
		await bot.reply_to(
			message, (
				"Please send me each file one at a time.\n\n"
				"I can process multiple files at once, but Telegram doesn’t reliably send me the files as a single batch. Because of that, I can’t tell whether all the files have arrived or if more are still coming.\n\n"
				"So, to make sure I process everything correctly, please send the files one at a time. I’m a little limited by how Telegram delivers them."
			)
		)
		return

	folder = await get_folder(user_id, message_id)

	if message.photo:
		file = message.photo[-1]
		size_mb = (file.file_size or 0) / (1024 * 1024)
		if size_mb <= MAX_SIZE_MB:
			file_path = await save_file(folder, message.photo[-1].file_id, "jpg")
		else:
			await bot.reply_to(message, f"Photo too large ({size_mb:.2f} MB)")
			return

	if message.video:
		file = message.video
		size_mb = (file.file_size or 0) / (1024 * 1024)
		if size_mb <= MAX_SIZE_MB:
			file_path = await save_file(folder, message.video.file_id, "mp4")
		else:
			await bot.reply_to(message, f"Video too large ({size_mb:.2f} MB)")
			return

	status_type = 'upload_photo' if media_type == 'photo' else 'upload_video'

	await bot.send_chat_action(
		chat_id=user_id,
		action=status_type
	)

	text_content = [
		{
			"type": "text",
			"text": caption
		}
	]

	if media_type == "photo":

		mime_type, _ = mimetypes.guess_type(file_path.name)
		mime_type = mime_type or "image/jpeg"

		with file_path.open("rb") as image_file:
			encoded_image = base64.b64encode(
				image_file.read()
			).decode("utf-8")
		img_content = [
			{
				"type": "image_url",
				"image_url": {
					"url": (
						f"data:{mime_type};base64,{encoded_image}"
					)
				}
			}
		]
		content = text_content + img_content if caption else img_content
		await ManageUsers.save_chat(
			user_id=user_id, 
			message_id=message_id, 
			message_type=media_type,
			role='user',
			content=json.dumps(content)
		)
		await orchestrate_response(user_id, status.message_id, media_type)

	elif media_type == "video":
		if video_semaphore.acquire(block=False):
			vid_content = [
				{
					"type": "video",
					"path": str(file_path)
				}
			]
			content = text_content + vid_content if caption else vid_content
			p = multiprocessing.Process(target=video_process_entry, args=(user_id, content, status.message_id))
			p.start()
		else:
			await bot.edit_message_text(
				chat_id=user_id,
				message_id=status.message_id,
				text="<i>Too many requests. Please try again in a few moments.</i>"
			)

async def main():
	await DatabaseArchitecture.create_all()
	await mqtt_handler.start_mqtt()
	await bot.polling()

asyncio.run(main())