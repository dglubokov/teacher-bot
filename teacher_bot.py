import asyncio
import time
import random
import os
import json

import torch
import requests
from dotenv import load_dotenv
from gtts import gTTS
from random_word import RandomWords
from random_word.services.wordnik import API_KEY
from telethon.sync import TelegramClient, events
from telethon.tl.custom import Conversation
from deep_translator import GoogleTranslator
from diffusers import StableDiffusionPipeline, LMSDiscreteScheduler


load_dotenv()

IMAGE_FILE_NAME = "temp.jpeg"

loop = asyncio.get_event_loop()

api_id = eval(os.environ["API_ID"])
api_hash = os.environ["API_HASH"]
bot_token = os.environ["BOT_TOKEN"]
bot = TelegramClient("teacher", api_id, api_hash).start(bot_token=bot_token)

lms = LMSDiscreteScheduler(
    beta_start=0.00085,
    beta_end=0.012,
    beta_schedule="scaled_linear"
)
token = os.environ["HUGGING_FACE"]
device = 'cuda' if torch.cuda.is_available() else 'cpu'
pipe = StableDiffusionPipeline.from_pretrained(
    "CompVis/stable-diffusion-v1-4",
    use_auth_token=token,
).to(device)


async def responser(conv: Conversation):
    try:
        # Wait for the response from user.
        response = await conv.get_response()
        return response
    except asyncio.exceptions.TimeoutError:
        await conv.send_message(
            "Your response time has expired 👀. You can re-enter your command at any time :)"
        )
        return False


# async def send_words():
@bot.on(events.NewMessage(pattern="/trigger"))
async def send_words(event):
    sender = "@dmglubokov"
    while True:
        r = RandomWords()
        t = GoogleTranslator(source='en', target='ru')
        time.sleep(1)

        while True:
            # Get word.
            word = r.get_random_word()
            time.sleep(1)
            if word is not None:
                break

        # Translate.
        translation = t.translate(word)
        s = f"{word} – {translation}\n\n"
        url = f"https://api.wordnik.com/v4/word.json/{word}/examples"
        r = requests.get(
            url,
            params={
                "includeDuplicates": "false",
                "useCanonical": "false",
                "limit": "3",
                "api_key": API_KEY
            }
        )
        print(r.json())
        response = r.json()["examples"]
        s += "__Examples:___\n\n" + "\n\n".join([r["text"] for r in response])
        await bot.send_message(sender, s)
        time.sleep(1)

        # Get image info.
        r = requests.get(
            "https://api.unsplash.com/search/photos/",
            params={
                "client_id": os.environ["UNSPLASH_ID"],
                "query": word,
                "page": 1
            }
        )
        results = r.json()["results"]
        time.sleep(1)

        # Send image if found.
        if len(results) > 0:
            url = results[0]["urls"]["small"]
            with requests.get(url, stream=True) as r:
                with open(IMAGE_FILE_NAME, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                with open(IMAGE_FILE_NAME, "rb") as f:
                    await bot.send_file(sender, f.read())
        else:
            try:
                prompt = f"{word} highly detailed 4k high resolution rendered volumetric lighting"
                image = pipe(prompt, num_inference_steps=30)["sample"][0]
                image.save(IMAGE_FILE_NAME)
                with open(IMAGE_FILE_NAME, "rb") as f:
                    await bot.send_file(sender, f.read())
            except Exception:
                await bot.send_message(sender, "__image not found__")

        # Check pronunciation
        gTTS(text=word, lang="en", slow=False).save("temp.mp3")
        await bot.send_file(sender, "temp.mp3", voice_note=True)

        with open("words.json") as f:
            words = json.load(f)
        words.append({
            "word": word,
            "translation": translation,
            "time_points": 2,
            "box": 1,
        })

        need_to_remember = []
        updated_words = []
        for word in words:
            word["time_points"] = word["time_points"] - 1
            if word["time_points"] == 0:
                need_to_remember.append(f'{word["word"]} – {word["translation"]}')
                word["box"] += 1
                word["time_points"] = 2 * word["box"]
            updated_words.append(word)
        with open("words.json", "w") as f:
            f.write(json.dumps(updated_words, ensure_ascii=False))

        if len(need_to_remember) > 0:
            s = "**remember these words**\n\n" + "\n".join(need_to_remember)
            await bot.send_message(sender, s)

        await asyncio.sleep(random.randrange(43200, 86400))


async def send_texts():
    sender = "@dmglubokov"
    while True:
        with open("texts.json") as f:
            texts = json.load(f)

        need_to_remember = []
        updated = []
        for text in texts:
            text["time_points"] = text["time_points"] - 1
            if text["time_points"] == 0:
                need_to_remember.append(text["text"])
                text["box"] += 1
                text["time_points"] = 2 * text["box"]
            updated.append(text)

        if len(need_to_remember) > 0:
            await bot.send_message(sender, "**Remember texts time!**")
            for text in need_to_remember:
                await bot.send_message(sender, text)

        with open("texts.json", "w") as f:
            f.write(json.dumps(updated, ensure_ascii=False))

        await asyncio.sleep(random.randrange(43200, 86400))


@bot.on(events.NewMessage(pattern="/add"))
async def add(event):
    sender = await event.get_sender()
    async with bot.conversation(sender) as conv:
        await conv.send_message("Add new card to remember")
        response = await responser(conv)
        if not response:
            return
        with open("texts.json") as f:
            texts = json.load(f)
        texts.append({
            "text": response.text,
            "time_points": 2,
            "box": 1,
        })
        with open("texts.json", "w") as f:
            f.write(json.dumps(texts, ensure_ascii=False))
        await conv.send_message("Added!")


@bot.on(events.NewMessage(pattern="/test"))
async def test(event):
    sender = await event.get_sender()
    await bot.send_message(sender, "it's working!")


try:
    print("(Press Ctrl+C to stop this)")
    # loop.create_task(send_words())
    # loop.create_task(send_texts())
    bot.run_until_disconnected()
finally:
    bot.disconnect()
