import logging
import os
from dotenv import load_dotenv
import asyncio
import aiohttp
from telebot.async_telebot import AsyncTeleBot
import time
import json
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
from strip_markdown import strip_markdown
from pathlib import Path
from uuid import uuid4
import random

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

from orchestrator import ORCHESTRATOR
from database_manager import DatabaseManager
from VoiceOrchestrator import STT, TTS

geolocator = Nominatim(user_agent="telegram_bot_locator")

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
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


@bot.message_handler(commands=['start'])
async def Assistant(message):
	user_id = message.from_user.id
	chat_id = message.chat.id

	first_name = message.from_user.first_name
	last_name = message.from_user.last_name or ""
	full_name = f"{first_name} {last_name}".strip()

	DBManager = DatabaseManager(user_id)
	DBManager.register_user(full_name)

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

	sent = await bot.send_message(
		chat_id,
		text,
		reply_markup=policy_keyboard,
		parse_mode="HTML"
	)
	start_message_id = sent.message_id
	# DBManager.save_chat(user_id, bot_message_id, text)


@bot.callback_query_handler(func=lambda call: call.data == "policy_accept")
async def handle_accept(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    DBManager = DatabaseManager(user_id)

    # DBManager.save_chat(user_id, message_id, "ACCEPT BUTTON CLICKED", "user")

    first_name = call.from_user.first_name
    last_name = call.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    memory = {
		'create': {
			'user_name': full_name
		}
    }
    DBManager.mamage_memory(memory)

    await bot.delete_message(
		chat_id=chat_id,
		message_id=message_id
	)

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

    await bot.send_message(
		chat_id,
		text,
		reply_markup=reply_keyboard,
		parse_mode="HTML"
	)

@bot.message_handler(content_types=['location', 'contact'])
async def handle_location(message):

	user_id = message.from_user.id
	chat_id = message.chat.id
	message_id = message.message_id

	DBManager = DatabaseManager(user_id)

	if message.location: 
		await bot.send_chat_action(
			chat_id=chat_id,
			action='find_location'
		)

		loc = message.location
		
		try:
			Coordinates = geolocator.reverse((loc.latitude, loc.longitude), language='en')
			if Coordinates:
				address = Coordinates.raw.get('address', {})
				postal_code = address.get('postcode')
				city = address.get('city') or address.get('town') or address.get('village')
				state = address.get('state')
				country = address.get('country')
				location = f"{city}, {state}, {country}"
				if postal_code:
					location += f"\nPostal Code: {postal_code}"

				# DBManager.save_chat(user_id, message_id, location, 'user')
				DBManager.update_location(f"{location}\nlatitude: {loc.latitude}, \nlongitude: {loc.longitude}")
				
				memory = {
					'create': {
						'location': location, 
						"home_coordinates": {
						"latitude": loc.latitude,
						"longitude": loc.longitude
						}
					}
				}
				DBManager.mamage_memory(memory)
				
		except Exception:
			text = (
				"📍 <b>Location Received</b>\n\n"
				"We received your location, but couldn't determine your address. 😓\n\n"
				"Please try sharing your location again."
			)
			
	elif message.contact:
		
		contact_info = message.contact
		contact = contact_info.phone_number
		DBManager.update_phone(contact)

		# DBManager.save_chat(user_id, message_id, contact, 'user')

		memory = {
			'create': {
				'phone_number': contact
			}
		}
		DBManager.mamage_memory(memory)

	confirmation = DBManager.ph_loc()
	con_loc = "Contact" if confirmation[0] else "Location"
	null_data = "Location" if con_loc == "Contact" else "Contact"
	text = (
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

		await bot.reply_to(
			message,
			text,
			parse_mode="HTML",
			reply_markup=reply_keyboard
		)

	elif confirmation[0] and confirmation[-1]:

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

	gender = call.data

	await bot.delete_message(
		chat_id=chat_id,
		message_id=message_id
	)

	text = """
<b>Oh, hey 👋</b>

I’m <b>Will</b>.

Think of me as your <i>homie</i>, or your <i>favorite AI troublemaker</i> 😂, depending on what kind of trouble we’re causing.

I can help you <b>control your smart spaces</b>, <b>automate things</b>, <b>create images and videos</b>, <b>compose music</b>, <b>build stuff</b>, <b>shop</b>, <b>manage projects</b>… pretty much whatever you throw at me.

<blockquote>Anywayyy, enough of the introduction.</blockquote>

<b>What’s up?</b>
"""

	await bot.send_message(
		chat_id,
		text,
		parse_mode="HTML",
		reply_markup=ReplyKeyboardRemove()
	)

	DBManager = DatabaseManager(user_id)
	DBManager.save_chat(user_id, chat_id, text)

	memory = {
		"create": {
		"Gender": gender
		}
	}

	DBManager.mamage_memory(memory)
			
@bot.callback_query_handler(func=lambda call: call.data == "policy_decline")
async def handle_reject(call):
	user_id = call.from_user.id
	chat_id = call.message.chat.id
	message_id = call.message.message_id

	# DatabaseManager.save_chat(user_id, message_id, "DECLINE BUTTON CLICKED", 'user')

	text = (
		"🚫 <b>Access Denied</b>\n\n"
		"You must accept our Privacy Policy and Consent Agreement to continue using the platform."
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

	# sent = await bot.send_message(
    #     chat_id,
    #     text,
    #     parse_mode="HTML",
	# 	reply_markup=policy_keyboard
    # )


async def transmition(chat_id, text):
    await bot.send_message(
        chat_id,
        text,
        parse_mode="HTML"
    )

async def AI_status(msg_type, chat_id):
	if msg_type == 'text':
		await bot.send_chat_action(
			chat_id=chat_id,
			action='typing'
		)
	else:
		await bot.send_chat_action(
			chat_id=chat_id,
			action='record_voice'
		)

async def orchestrate_response(user_id, chat_id, msg_type='text'):

	if msg_type == 'text':
		status = await bot.send_message(chat_id, "<i>Processing...</i>", parse_mode="HTML")
	elif msg_type in ['audio', 'voice']:
		status = await bot.send_message(chat_id, f"<i>Generating {msg_type} response...</i>", parse_mode="HTML")
	bot_message_id = status.message_id

	await AI_status(msg_type, chat_id)

	tool_call, first_stream = False, True

	while True:
		response, stream_buffer = "", ""
		last_stream = time.time()
		STREAM_INTERVAL = 0.5
		LLM = ORCHESTRATOR(user_id)
		loop = False
		async for chunk in LLM.orchestrator():
			if isinstance(chunk, dict) and len(str(chunk) )>= 53:
				if chunk.get("tool_status_message"):
					await bot.edit_message_text(
						chat_id=chat_id,
						message_id=bot_message_id,
						text=chunk["tool_status_message"],
						parse_mode="HTML"
					)
					await AI_status(msg_type, chat_id)
					loop = True
			elif isinstance(chunk, list) and len(str(chunk) )>= 42:
				for transmit in tool_call.get('transmit', ''):
					transmition(list(transmit.keys())[0], list(transmit.values())[0])

			else:
				response += chunk
				stream_buffer += chunk
				# stream_buffer = strip_markdown(stream_buffer)
				stream_buffer = BeautifulSoup(stream_buffer, "html.parser").get_text()
				if msg_type == 'text':
					now = time.time()
					if first_stream or now - last_stream >= STREAM_INTERVAL:
						try:
							await bot.edit_message_text(
								chat_id=chat_id,
								message_id=bot_message_id,
								text=stream_buffer
							)
							last_stream, first_stream = now, False
						except Exception as inner_e:
							logger.warning(f"Error during streaming: {repr(inner_e)}")
		if not loop:
			break
# ====================================================
	try:
		if msg_type == 'text':
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=bot_message_id,
				text=response or "<b>🫡 Your request has been processed.</b>",
				parse_mode="HTML"
			)
		elif msg_type in ['audio', 'voice']:

			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=bot_message_id,
				text=f"<i>Finalizing {msg_type} response...</i>",
				parse_mode="HTML"
			)

			await bot.send_chat_action(
				chat_id=chat_id,
				action='upload_voice'
			)
			
			transcription = BeautifulSoup(response, "html.parser").get_text()
			voice_path = TTS(user_id, transcription)
			voice_note, Vtype = await voice_path.VoicePath()

			await bot.delete_message(chat_id, bot_message_id)

			if Vtype == 'voice':
				with open(voice_note, "rb") as voice:
					await bot.send_voice(
						chat_id=chat_id,
						voice=voice
						# caption="🎤 Here's your voice note."
					)
			else:
				with open(voice_note, "rb") as audio:
					await bot.send_audio(
						chat_id=chat_id,
						audio=audio
						# caption="🎵 Here's your audio."
					)
		
		DatabaseManager.save_chat(user_id, bot_message_id, response)

	except Exception as e:
		logger.warning(f"Response delivery failed: {repr(e)}")
		# response = strip_markdown(response)
		fallback_msg = BeautifulSoup(response, "html.parser").get_text()
		try:
			await bot.edit_message_text(
				chat_id=chat_id,
				message_id=bot_message_id,
				text=fallback_msg
			)

		except Exception as inner_e:
			logger.error(f"Unexpected delivery error: {repr(inner_e)}")
			fallback_msg = "⚠️ <b>An error occurred while generating your response. Please try sending your message again.</b>"


			await bot.send_message(chat_id, fallback_msg, parse_mode="HTML")
		DatabaseManager.save_chat(user_id, bot_message_id, fallback_msg)

@bot.message_handler(func=lambda message: True)
async def assistant(message):
	user_id = message.from_user.id
	chat_id = message.chat.id
	message_id = message.message_id
	msg = message.text
	DatabaseManager.save_chat(user_id, message_id, msg, "user")
	await orchestrate_response(user_id, chat_id)

@bot.message_handler(content_types=['audio', 'voice'])
async def voice_messager(message):
	user_id = message.from_user.id
	chat_id = message.chat.id
	message_id = message.message_id
	msg = message.text

	await bot.send_chat_action(
		chat_id=chat_id,
		action='upload_voice'
	)

	BASE_AUDIO_DIR = Path("AudioClips")
	user_dir = BASE_AUDIO_DIR / str(user_id)
	user_dir.mkdir(parents=True, exist_ok=True)

	file = message.voice or message.audio

	file_info = await bot.get_file(file.file_id)
	downloaded_file = await bot.download_file(file_info.file_path)

	file = [
		int(f.stem.replace("AudioClip", ""))
		for f in user_dir.glob("AudioClip*.ogg")
	]
	fileNum = max(file, default=0) + 1

	audio_path = user_dir / f"AudioClip{fileNum}.ogg"

	with open(audio_path, "wb") as f:
		f.write(downloaded_file)

	transcriber = STT(audio_path)
	transcribe = await transcriber.transcribe()

	DatabaseManager.save_chat(user_id, message_id, transcribe, "user", "audio")
	await orchestrate_response(user_id, chat_id, "voice" if message.voice else "audio")


print("Telegram Bot initialized")
asyncio.run(bot.polling())