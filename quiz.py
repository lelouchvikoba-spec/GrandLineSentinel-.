# quiz.py
"""Random three-choice character quiz and reward flow."""
import asyncio
import random
import time
import uuid

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID
from data_manager import (
    get_player,
    save_data,
    active_challenges,
    normal_characters,
    mythical_characters,
    exalted_characters,
    get_character_rarities,
    get_rarity_emoji,
    get_rarity_reward_range,
    get_quiz_rarities,
    set_quiz_rarities,
)
from utils import get_xp_needed


# One active question per chat. A short token prevents old buttons from
# accidentally answering a newer question in the same chat.
ACTIVE_QUIZZES = {}
MANUAL_QUIZZES = {}
QUIZ_TIMEOUT = 300
QUIZ_MIN_MESSAGES = 80
QUIZ_MAX_MESSAGES = 220
AUTO_QUIZ_ENABLED = True
_quiz_message_counts = {}
_quiz_next_spawn = {}

QUESTIONS = (
    # One Piece
    ("What is the name of Luffy's first ship?", ("Going Merry", "Thousand Sunny", "Red Force"), 0),
    ("Who is the swordsman of the Straw Hat crew?", ("Sanji", "Roronoa Zoro", "Usopp"), 1),
    ("What is the name of the treasure sought by pirates?", ("One Piece", "All Blue", "Rio Poneglyph"), 0),
    ("Which sea is Luffy originally from?", ("North Blue", "East Blue", "West Blue"), 1),
    ("Who is the navigator of the Straw Hat crew?", ("Nami", "Robin", "Vivi"), 0),
    ("What is Chopper?", ("A reindeer", "A shark", "A bird"), 0),
    ("Who is known as the Pirate Hunter?", ("Trafalgar Law", "Roronoa Zoro", "Eustass Kid"), 1),
    ("What power does a Devil Fruit user lose in the sea?", ("The ability to swim", "Their memory", "Their Haki"), 0),
    ("Who is the captain of the Straw Hat Pirates?", ("Portgas D. Ace", "Monkey D. Luffy", "Shanks"), 1),
    ("What is Sanji's fighting style mainly based on?", ("His hands", "His feet", "A sword"), 1),
    # Bleach
    ("What is the name of Ichigo Kurosaki's Zanpakuto?", ("Zangetsu", "Senbonzakura", "Hyorinmaru"), 0),
    ("Who is the captain of Squad 6 in Bleach?", ("Byakuya Kuchiki", "Kenpachi Zaraki", "Toshiro Hitsugaya"), 0),
    ("What are Soul Reapers called in Japanese?", ("Shinigami", "Quincy", "Arrancar"), 0),
    # Naruto
    ("What is Naruto Uzumaki's signature technique?", ("Rasengan", "Chidori", "Amaterasu"), 0),
    ("Which village is Naruto from?", ("Hidden Leaf Village", "Hidden Sand Village", "Hidden Mist Village"), 0),
    ("Who is Naruto's rival from the Uchiha clan?", ("Sasuke Uchiha", "Shikamaru Nara", "Neji Hyuga"), 0),
    # Jujutsu Kaisen
    ("Who is the strongest modern sorcerer in Jujutsu Kaisen?", ("Satoru Gojo", "Kento Nanami", "Suguru Geto"), 0),
    ("What is the name of Yuji Itadori's cursed companion?", ("Ryomen Sukuna", "Mahito", "Jogo"), 0),
    ("What is Megumi Fushiguro's main technique?", ("Ten Shadows Technique", "Boogie Woogie", "Ratio Technique"), 0),
    # Hunter x Hunter
    ("What is the name of Gon Freecss's father?", ("Ging Freecss", "Isaac Netero", "Silva Zoldyck"), 0),
    ("What is Killua Zoldyck's family known for?", ("Assassins", "Pirates", "Alchemists"), 0),
    ("What energy system is used in Hunter x Hunter?", ("Nen", "Reiatsu", "Chakra"), 0),
    # Math
    ("What is 12 × 8?", ("86", "96", "108"), 1),
    ("What is the square root of 144?", ("10", "12", "14"), 1),
    ("What is 25% of 200?", ("25", "50", "75"), 1),
)


# Existing questions are the introductory/easy pool. The larger hard pool
# keeps quizzes varied while choosing difficulty at a 30% / 70% ratio.
EASY_QUESTIONS = QUESTIONS + (
    ("What is the name of Luffy's father?", ("Monkey D. Dragon", "Gol D. Roger", "Monkey D. Garp"), 0),
    ("Which Straw Hat is the crew's doctor?", ("Chopper", "Franky", "Brook"), 0),
    ("What is the name of the village Naruto grew up in?", ("Konoha", "Suna", "Kiri"), 0),
    ("Which Pokémon does Ash start with in the original anime?", ("Pikachu", "Charmander", "Squirtle"), 0),
    ("Who is the captain of the Survey Corps in Attack on Titan?", ("Levi Ackerman", "Jean Kirstein", "Reiner Braun"), 0),
    ("What is the name of Tanjiro's sister?", ("Nezuko", "Mitsuri", "Kanao"), 0),
    ("Which ninja team is Kakashi assigned to lead?", ("Team 7", "Team 10", "Team Guy"), 0),
    ("What is the name of the school in My Hero Academia?", ("U.A. High School", "Tokyo Jujutsu High", "Shiketsu Academy"), 0),
    ("What is Saitama's hero alias in One-Punch Man?", ("Caped Baldy", "Silver Fang", "Demon Cyborg"), 0),
    ("Who is the alchemist known as the Fullmetal Alchemist?", ("Edward Elric", "Alphonse Elric", "Roy Mustang"), 0),
)

HARD_QUESTIONS = (
    ("Which poneglyph records the location of an Ancient Weapon?", ("Road Poneglyph", "Rio Poneglyph", "Blue Poneglyph"), 1),
    ("What was the name of the ship Gol D. Roger sailed before the Oro Jackson?", ("Polar Tang", "The Oro Jackson was his only ship", "The Moby Dick"), 1),
    ("Who was the first commander of the Whitebeard Pirates?", ("Marco", "Oden", "Jozu"), 1),
    ("Which organization did Nico Robin belong to before joining the Straw Hats?", ("Baroque Works", "CP9", "Donquixote Pirates"), 0),
    ("What is the name of Law's submarine?", ("Polar Tang", "Victoria Punk", "Nostra Castello"), 0),
    ("Which Bleach character is the former captain of Squad 12 and founder of the Shinigami Research Institute?", ("Kisuke Urahara", "Mayuri Kurotsuchi", "Shinji Hirako"), 0),
    ("What is the name of Byakuya Kuchiki's Bankai?", ("Senbonzakura Kageyoshi", "Katen Kyokotsu", "Daiguren Hyorinmaru"), 0),
    ("Which Quincy technique lets its user manipulate reishi in the environment?", ("Blut Vene", "Hirenkyaku", "Ransotengai"), 1),
    ("Who was the Third Hokage's teacher?", ("Tobirama Senju", "Hashirama Senju", "Hiruzen Sarutobi"), 1),
    ("Which tailed beast is sealed inside Gaara?", ("Shukaku", "Matatabi", "Isobu"), 0),
    ("What is the name of the space-time technique used by Minato?", ("Flying Thunder God Technique", "Body Flicker Technique", "Kamui"), 0),
    ("Which member of the Akatsuki partnered with Sasori?", ("Deidara", "Kisame", "Hidan"), 0),
    ("In Jujutsu Kaisen, what is the name of Gojo's domain expansion?", ("Unlimited Void", "Malevolent Shrine", "Coffin of the Iron Mountain"), 0),
    ("Which cursed technique belongs to Aoi Todo?", ("Boogie Woogie", "Ratio Technique", "Idle Transfiguration"), 0),
    ("What is the name of Megumi's shikigami formed from a pair of dogs?", ("Divine Dogs", "Nue", "Max Elephant"), 0),
    ("Who was the chairman of the Hunter Association during the Chimera Ant arc?", ("Isaac Netero", "Cheadle Yorkshire", "Pariston Hill"), 0),
    ("What is the name of Killua's older brother who uses needles to control people?", ("Illumi", "Milluki", "Kalluto"), 0),
    ("Which Nen category is most naturally suited to creating aura constructs?", ("Conjuration", "Emission", "Enhancement"), 0),
    ("In Fullmetal Alchemist, what is the name of the country where the Elric brothers live?", ("Amestris", "Xing", "Drachma"), 0),
    ("What is the name of Roy Mustang's lieutenant?", ("Riza Hawkeye", "Winry Rockbell", "Olivier Armstrong"), 0),
    ("Which Titan power did Grisha Yeager pass to Eren?", ("Attack Titan", "Female Titan", "Jaw Titan"), 0),
    ("What is the name of the first opening theme of Neon Genesis Evangelion?", ("A Cruel Angel's Thesis", "Beautiful World", "Komm, süsser Tod"), 0),
    ("Which JoJo part features the Stand Killer Queen?", ("Part 4: Diamond Is Unbreakable", "Part 3: Stardust Crusaders", "Part 5: Golden Wind"), 0),
    ("What is the name of Goku's father?", ("Bardock", "King Vegeta", "Raditz"), 0),
    ("Which Death Note character is known as the world's second L?", ("Near", "Mello", "Light Yagami"), 0),
    ("In arithmetic, what is the least common multiple of 18 and 24?", ("72", "48", "96"), 0),
    ("What is 15% of 360?", ("54", "45", "60"), 0),
    ("If 3x + 7 = 31, what is x?", ("8", "7", "9"), 0),
    ("What is the sum of the interior angles of a hexagon?", ("720°", "540°", "900°"), 0),
    ("A fair six-sided die is rolled twice. What is the probability of getting a total of 7?", ("1/6", "1/12", "1/3"), 0),
    # Hunter × Hunter — detailed Nen mechanics
    ("When Knuckle's target goes bankrupt under Hakoware, what does A.P.R. become and what does it do?", ("I.R.S.; it forces the target into continuous Zetsu for 30 days", "Deep Purple; it seals the target's aura for one hour", "Hide and Seek; it traps the target in a Nen room"), 0),
    ("While Knuckle's target remains within 50 meters, how often does A.P.R. add interest, and at what rate?", ("10% every 10 seconds", "5% every minute", "10% every 30 seconds"), 0),
    ("What does the acronym A.P.R. stand for in Knuckle's Hakoware ability?", ("Amortizing Power Redirector", "Aura Payment Reversal", "Automatic Penalty Receiver"), 0),
    ("What event can cancel Knuckle's Hakoware aside from Nen exorcism?", ("Knuckle being rendered unconscious", "The target leaving Knuckle's sight", "The target using any emitted aura"), 0),
    ("Under Hakoware, what happens when the target hits Knuckle while A.P.R. is attached?", ("The target returns aura to Knuckle, reducing the debt", "Knuckle takes normal damage and the debt doubles", "A.P.R. transfers the target's Nen ability to Knuckle"), 0),
    ("Which Nen ability lets Knov enter and move through his conjured Nen dimension?", ("Hide and Seek", "Scream", "Crazy Slots"), 0),
    ("What does Kite's Crazy Slots conjure?", ("A randomly selected weapon", "A set of numbered chains", "A smoke puppet controlled by a pipe"), 0),
    ("In Gon's Jajanken, which Nen category primarily powers 'Paper'?", ("Emission", "Transmutation", "Manipulation"), 0),
    ("In Gon's Jajanken, which Nen category primarily powers 'Scissors'?", ("Transmutation", "Conjuration", "Enhancement"), 0),
)


def _choose_question():
    """Select easy/hard at 30/70 odds, then pick randomly within that pool."""
    pool = EASY_QUESTIONS if random.random() < 0.30 else HARD_QUESTIONS
    return random.choice(pool)


def _all_characters():
    return normal_characters + mythical_characters + exalted_characters


def _available_reward_pool():
    configured = get_quiz_rarities()
    allowed = set(configured) if configured else set(get_character_rarities())
    return [
        character for character in _all_characters()
        if str(character.get("rarity", "NORMAL")).strip().upper() in allowed
    ]


def _question_markup(token, options):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"A. {options[0]}", callback_data=f"quiz:{token}:0")],
        [InlineKeyboardButton(f"B. {options[1]}", callback_data=f"quiz:{token}:1")],
        [InlineKeyboardButton(f"C. {options[2]}", callback_data=f"quiz:{token}:2")],
    ])


def _manual_question_markup(token, chat_id, options):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"A. {options[0]}", callback_data=f"manualquiz:{token}:{chat_id}:0")],
        [InlineKeyboardButton(f"B. {options[1]}", callback_data=f"manualquiz:{token}:{chat_id}:1")],
        [InlineKeyboardButton(f"C. {options[2]}", callback_data=f"manualquiz:{token}:{chat_id}:2")],
    ])


def _question_text(question):
    return (
        "🧠 **CHARACTER QUIZ**\n\n"
        f"**{question}**\n\n"
        "Choose the correct answer to make a random character appear!\n"
        f"⏳ Expires in {QUIZ_TIMEOUT // 60} minutes"
    )


def _format_rarity_list():
    configured = get_quiz_rarities()
    if not configured:
        return "All rarities with available characters"
    return ", ".join(f"{get_rarity_emoji(r)} {r}" for r in configured)


def _parse_rarity_names(raw):
    """Parse comma/pipe-separated names, preserving custom names with spaces."""
    known = get_character_rarities()
    lookup = {" ".join(str(name).upper().split()): name for name in known}
    pieces = [part.strip() for part in raw.replace("|", ",").split(",") if part.strip()]
    if len(pieces) == 1 and " " in pieces[0]:
        words = pieces[0].split()
        pieces = []
        index = 0
        while index < len(words):
            match = None
            for end in range(len(words), index, -1):
                candidate = " ".join(words[index:end]).upper()
                if candidate in lookup:
                    match = (end, candidate)
                    break
            if not match:
                pieces.append(" ".join(words[index:]))
                break
            pieces.append(match[1])
            index = match[0]
    normalized = []
    invalid = []
    for piece in pieces:
        value = " ".join(piece.upper().split())
        if value in lookup:
            canonical = lookup[value]
            if canonical not in normalized:
                normalized.append(canonical)
        else:
            invalid.append(piece)
    return normalized, invalid


async def _send_reward(client, message, user, character):
    rarity = str(character.get("rarity", "NORMAL")).upper()
    low, high = get_rarity_reward_range(rarity)
    bounty = random.randint(low, high)
    xp_reward = 500 if rarity == "MYTHICAL" else 100
    user.captured_chars.append({
        "id": character.get("id"),
        "name": character.get("name", "Unknown"),
        "image": character.get("image"),
        "media_type": character.get("media_type", "photo"),
        "rarity": rarity,
        "captured_at": time.time(),
    })
    user.bounty += bounty
    user.xp += xp_reward
    old_level = user.level
    while user.level < 200 and user.xp >= get_xp_needed(user.level):
        user.xp -= get_xp_needed(user.level)
        user.level += 1
    save_data()

    level_note = f"\n📈 Level up: {old_level} → {user.level}" if user.level > old_level else ""
    caption = (
        "🎉 **CORRECT ANSWER!**\n\n"
        f"{get_rarity_emoji(rarity)} **{character.get('name', 'Unknown')}** dropped!\n"
        f"🆔 Character ID: `{character.get('id', 'N/A')}`\n"
        f"🏷️ Rarity: **{rarity}**\n\n"
        f"🎁 Bounty: **+฿{bounty:,}**\n"
        f"✨ XP: **+{xp_reward}**{level_note}"
    )
    media = character.get("image")
    if media:
        if character.get("media_type") == "video":
            try:
                await client.send_video(message.chat.id, media, caption=caption)
                return
            except Exception:
                pass
        for method in ("send_photo", "send_document"):
            try:
                await getattr(client, method)(message.chat.id, media, caption=caption)
                return
            except Exception:
                pass
    await client.send_message(message.chat.id, caption)


def _schedule_next_quiz(chat_id):
    """Choose a fresh random activity threshold for a group."""
    _quiz_message_counts[chat_id] = 0
    _quiz_next_spawn[chat_id] = random.randint(QUIZ_MIN_MESSAGES, QUIZ_MAX_MESSAGES)


def _quiz_is_active(chat_id):
    quiz = ACTIVE_QUIZZES.get(chat_id)
    if not quiz:
        return False
    if time.time() - quiz.get("created_at", 0) >= QUIZ_TIMEOUT:
        ACTIVE_QUIZZES.pop(chat_id, None)
        return False
    return True


_manual_timeout_tasks = {}


def _manual_quiz_is_active(chat_id):
    quiz = MANUAL_QUIZZES.get(chat_id)
    if not quiz:
        return False
    if time.time() - quiz.get("created_at", 0) >= QUIZ_TIMEOUT:
        MANUAL_QUIZZES.pop(chat_id, None)
        return False
    return True


def _cancel_manual_timeout(chat_id):
    task = _manual_timeout_tasks.pop(chat_id, None)
    if task and task is not asyncio.current_task() and not task.done():
        task.cancel()


async def _start_manual_reward_quiz(client, chat_id):
    question, options, correct = _choose_question()
    token = uuid.uuid4().hex[:10]
    MANUAL_QUIZZES[chat_id] = {
        "token": token, "question": question, "options": options,
        "correct": correct, "created_at": time.time(), "chat_id": chat_id,
    }
    await client.send_message(
        chat_id,
        "🎯 **MANUAL REWARD QUIZ**\n\n"
        f"**{question}**\n\n"
        "Everyone can answer. Correct answer gives one random reward:\n"
        "💰 Bounty • ⚡ 2x XP Boost • 🛡️ Shield\n\n"
        f"⏳ Answer time: {QUIZ_TIMEOUT // 60} minutes\n"
        "The next quiz appears after a wrong answer, correct answer, or timeout.\n"
        "Use `/quickquiz stop` to stop the quiz.",
        reply_markup=_manual_question_markup(token, chat_id, options),
    )
    _cancel_manual_timeout(chat_id)
    _manual_timeout_tasks[chat_id] = asyncio.create_task(
        _manual_quiz_timeout(client, chat_id, token)
    )


async def _manual_quiz_timeout(client, chat_id, token):
    try:
        await asyncio.sleep(QUIZ_TIMEOUT)
        quiz = MANUAL_QUIZZES.get(chat_id)
        if not quiz or quiz.get("token") != token:
            return
        MANUAL_QUIZZES.pop(chat_id, None)
        _manual_timeout_tasks.pop(chat_id, None)
        await client.send_message(chat_id, "⏰ Time is over! A new quickquiz is starting.")
        await _start_manual_reward_quiz(client, chat_id)
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        print(f"[manual quiz timeout] {exc}")


async def start_manual_quiz(client, message):
    """Start a shared player quiz that is never created by the auto scheduler."""
    chat_id = message.chat.id
    if _manual_quiz_is_active(chat_id):
        await message.reply("❌ A quickquiz is already active here. Everyone can answer it!")
        return
    await _start_manual_reward_quiz(client, chat_id)


async def handle_manual_quiz_callback(client, callback):
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Invalid quiz button.", show_alert=True)
        return
    try:
        quiz_chat_id = int(parts[2])
        choice = int(parts[3])
    except ValueError:
        await callback.answer("Invalid answer.", show_alert=True)
        return
    if callback.message.chat.id != quiz_chat_id:
        await callback.answer("This quiz belongs to another chat.", show_alert=True)
        return
    quiz = MANUAL_QUIZZES.get(quiz_chat_id)
    if not quiz or quiz.get("token") != parts[1] or time.time() - quiz["created_at"] >= QUIZ_TIMEOUT:
        MANUAL_QUIZZES.pop(quiz_chat_id, None)
        await callback.answer("This manual quiz has expired.", show_alert=True)
        return
    if choice != quiz["correct"]:
        MANUAL_QUIZZES.pop(quiz_chat_id, None)
        _cancel_manual_timeout(quiz_chat_id)
        await callback.answer("❌ You're wrong! A new quiz is starting.", show_alert=True)
        try:
            await callback.message.edit_text(
                "❌ **YOU'RE WRONG!**\n\n"
                f"{callback.from_user.mention} selected the wrong answer.\n"
                "No reward was given. A new quickquiz is starting."
            )
        except Exception:
            await callback.message.edit_reply_markup(reply_markup=None)
        await _start_manual_reward_quiz(client, quiz_chat_id)
        return

    MANUAL_QUIZZES.pop(quiz_chat_id, None)
    _cancel_manual_timeout(quiz_chat_id)
    player = get_player(callback.from_user.id, user=callback.from_user)
    reward = random.choice(("bounty", "boost", "shield"))
    if reward == "bounty":
        amount = random.randint(50_000, 500_000)
        player.bounty += amount
        reward_text = f"💰 Bounty: **+฿{amount:,}**"
    elif reward == "boost":
        player.boost_end = max(float(getattr(player, "boost_end", 0) or 0), time.time()) + 900
        reward_text = "⚡ **2x XP Boost** for 15 minutes"
    else:
        player.shields.append({"level": 1, "uses": 3, "purchased_at": time.time()})
        reward_text = "🛡️ **Shield Lv1** (3 uses)"
    save_data()
    await callback.answer("✅ Correct!", show_alert=False)
    try:
        await callback.message.edit_text(
            "🎉 **MANUAL QUIZ COMPLETE!**\n\n"
            f"{callback.from_user.mention} got the answer right!\n"
            f"Random reward: {reward_text}"
        )
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)
    await _start_manual_reward_quiz(client, quiz_chat_id)


async def start_quiz(client, chat_id):
    """Start a quiz in a chat if the reward pool and chat are eligible."""
    if _quiz_is_active(chat_id):
        return False
    pool = _available_reward_pool()
    if not pool:
        return False
    question, options, correct = _choose_question()
    token = uuid.uuid4().hex[:10]
    ACTIVE_QUIZZES[chat_id] = {
        "token": token,
        "question": question,
        "options": options,
        "correct": correct,
        "created_at": time.time(),
    }
    from quiz_media import get_quiz_drop_media
    media = get_quiz_drop_media()
    sticker = media.get("sticker")
    if sticker:
        try:
            await client.send_sticker(chat_id, sticker)
        except Exception as exc:
            print(f"[auto quiz sticker] {exc}")
    emoji = media.get("emoji")
    if emoji:
        try:
            await client.send_message(chat_id, emoji)
        except Exception as exc:
            print(f"[auto quiz emoji] {exc}")
    gif = media.get("gif")
    if gif:
        try:
            await client.send_animation(chat_id, gif)
        except Exception as exc:
            print(f"[auto quiz GIF] {exc}")
    await client.send_message(
        chat_id,
        _question_text(question),
        reply_markup=_question_markup(token, options),
    )
    return True


async def spawn_quiz_character(client, chat_id, chat_name="Group"):
    """Spawn a normal challengeable character after a correct quiz answer."""
    if chat_id in active_challenges:
        await client.send_message(
            chat_id,
            "✅ Correct answer! A character is already active here, so answer its challenge first.",
        )
        return False

    pool = _available_reward_pool()
    if not pool:
        await client.send_message(chat_id, "✅ Correct answer, but no quiz reward characters are configured.")
        return False

    character = random.choice(pool)
    rarity = str(character.get("rarity", "NORMAL")).upper()
    emoji = get_rarity_emoji(rarity)
    low, high = get_rarity_reward_range(rarity)
    reward = f"฿{low:,}–฿{high:,} + XP"
    if rarity == "MYTHICAL":
        reward += " + 1 Token"
    caption = (
        f"{emoji} **A {rarity.title()} Character Appeared From The Quiz!**\n\n"
        "Character: ???\n"
        f"Type: {rarity}\n"
        f"Reward: {reward}\n\n"
        "Despawns in 5 min\n"
        "Type `/challenge [name]` to fight!"
    )
    active_challenges[chat_id] = {
        "char": character,
        "is_mythical": rarity == "MYTHICAL",
        "rarity": rarity,
        "challenger": None,
        "spawn_time": time.time(),
        "chat_name": chat_name or "Group",
    }
    media = character.get("image")
    if media:
        if character.get("media_type") == "video":
            try:
                await client.send_video(chat_id, media, caption=caption)
                return True
            except Exception:
                pass
        for method in ("send_photo", "send_document"):
            try:
                await getattr(client, method)(chat_id, media, caption=caption)
                return True
            except Exception:
                pass
    await client.send_message(chat_id, caption)
    return True


async def maybe_start_random_quiz(client, chat_id):
    """Advance a group's random quiz timer and occasionally post a quiz."""
    if not AUTO_QUIZ_ENABLED:
        return False
    if chat_id not in _quiz_next_spawn:
        _schedule_next_quiz(chat_id)
    if _quiz_is_active(chat_id):
        return False
    _quiz_message_counts[chat_id] = _quiz_message_counts.get(chat_id, 0) + 1
    if _quiz_message_counts[chat_id] < _quiz_next_spawn[chat_id]:
        return False
    started = await start_quiz(client, chat_id)
    _schedule_next_quiz(chat_id)
    return started


def register_quiz(app):
    @app.on_message(filters.command("setquizsticker"))
    async def set_quiz_sticker_cmd(client, message):
        if not message.from_user or message.from_user.id != OWNER_ID:
            await message.reply("⛔ Owner only.")
            return
        args = (message.text or message.caption or "").split(maxsplit=1)
        file_id = args[1].strip() if len(args) > 1 else ""
        if not file_id and message.reply_to_message:
            media_message = message.reply_to_message
            if media_message.sticker:
                file_id = media_message.sticker.file_id
        if not file_id:
            await message.reply("Reply to a Telegram sticker with `/setquizsticker`, or pass its file ID.")
            return
        from quiz_media import set_quiz_drop_media
        set_quiz_drop_media("sticker", file_id)
        await message.reply("✅ Saved. This sticker will be sent before each auto-quiz drop message.")

    @app.on_message(filters.command("setquizgif"))
    async def set_quiz_gif_cmd(client, message):
        if not message.from_user or message.from_user.id != OWNER_ID:
            await message.reply("⛔ Owner only.")
            return
        args = (message.text or message.caption or "").split(maxsplit=1)
        file_id = args[1].strip() if len(args) > 1 else ""
        if not file_id and message.reply_to_message:
            media_message = message.reply_to_message
            if media_message.animation:
                file_id = media_message.animation.file_id
            elif media_message.document and (
                (media_message.document.mime_type or "").lower() == "image/gif"
                or (media_message.document.file_name or "").lower().endswith(".gif")
            ):
                file_id = media_message.document.file_id
        if not file_id:
            await message.reply("Reply to a Telegram GIF/animation with `/setquizgif`, or pass its file ID.")
            return
        from quiz_media import set_quiz_drop_media
        set_quiz_drop_media("gif", file_id)
        await message.reply("✅ Saved. This GIF will be sent before each auto-quiz drop message.")

    @app.on_message(filters.command("setquizemoji"))
    async def set_quiz_emoji_cmd(client, message):
        if not message.from_user or message.from_user.id != OWNER_ID:
            await message.reply("⛔ Owner only.")
            return
        args = (message.text or message.caption or "").split(maxsplit=1)
        if len(args) < 2 or not args[1].strip():
            await message.reply("Usage: `/setquizemoji [emoji]` or `/setquizemoji off` to clear it.")
            return
        from quiz_media import clear_quiz_drop_media, set_quiz_drop_media
        if args[1].strip().casefold() == "off":
            clear_quiz_drop_media("emoji")
            await message.reply("✅ Cleared the auto-quiz emoji.")
            return
        set_quiz_drop_media("emoji", args[1].strip())
        await message.reply("✅ Saved. This emoji will appear at the start of each auto-quiz drop message.")

    @app.on_message(filters.command("quizdropmedia"))
    async def quiz_drop_media_status_cmd(client, message):
        if not message.from_user or message.from_user.id != OWNER_ID:
            await message.reply("⛔ Owner only.")
            return
        from quiz_media import get_quiz_drop_media
        media = get_quiz_drop_media()
        await message.reply(
            "**AUTO-QUIZ DROP MEDIA**\n\n"
            f"Sticker: {'✅ Set' if media.get('sticker') else '❌ Not set'}\n"
            f"Emoji: {media.get('emoji', '❌ Not set')}\n"
            f"GIF: {'✅ Set' if media.get('gif') else '❌ Not set'}\n\n"
            "Clear them with `/clearquizsticker` or `/clearquizgif`; clear the emoji with `/setquizemoji off`."
        )

    @app.on_message(filters.command(["clearquizsticker", "clearquizgif"]))
    async def clear_quiz_media_cmd(client, message):
        if not message.from_user or message.from_user.id != OWNER_ID:
            await message.reply("⛔ Owner only.")
            return
        command = (message.command[0] if getattr(message, "command", None) else "").split("@", 1)[0]
        kind = "sticker" if command == "clearquizsticker" else "gif"
        from quiz_media import clear_quiz_drop_media
        if clear_quiz_drop_media(kind):
            await message.reply(f"✅ Cleared the auto-quiz {kind}.")
        else:
            await message.reply(f"ℹ️ No auto-quiz {kind} was configured.")

    @app.on_message(filters.command(["quickquiz", "manualquiz"]))
    async def quick_quiz_cmd(client, message):
        args = (message.text or "").split()
        if len(args) > 1 and args[1].casefold() == "stop":
            chat_id = message.chat.id
            if MANUAL_QUIZZES.pop(chat_id, None):
                _cancel_manual_timeout(chat_id)
                await message.reply("✅ The quickquiz was stopped for this chat.")
            else:
                await message.reply("ℹ️ There is no active quickquiz in this chat.")
            return
        await start_manual_quiz(client, message)

    @app.on_message(filters.command(["quiz", "question"]))
    async def quiz_cmd(client, message):
        global AUTO_QUIZ_ENABLED
        if not message.from_user or message.from_user.id != OWNER_ID:
            await message.reply("⛔ Only the bot owner can start a quiz manually.")
            return
        chat_id = message.chat.id
        args = (message.text or "").split()
        action = args[1].casefold() if len(args) > 1 else ""
        if action == "on":
            AUTO_QUIZ_ENABLED = True
            await message.reply("✅ Automatic quizzes are ON and will continue until the owner uses `/quiz off`.")
            return
        if action == "off":
            AUTO_QUIZ_ENABLED = False
            ACTIVE_QUIZZES.pop(chat_id, None)
            await message.reply("🛑 Automatic quizzes are OFF. Existing quiz in this chat was stopped.")
            return
        if action == "stop":
            if ACTIVE_QUIZZES.pop(chat_id, None):
                await message.reply("✅ The active quiz in this chat was stopped.")
            else:
                await message.reply("ℹ️ No active quiz in this chat.")
            return
        if action:
            await message.reply("Usage: `/quiz` to start, `/quiz on`, `/quiz off`, or `/quiz stop`.")
            return
        if _quiz_is_active(chat_id):
            await message.reply("❌ A quiz is already active here. Answer it first!")
            return
        if not await start_quiz(client, chat_id):
            await message.reply(
                "❌ No characters are available in the configured quiz rarities. "
                "Ask the owner to update `/setquizrarities`."
            )

    @app.on_message(filters.command(["quizrarities", "quizpool"]))
    async def quiz_rarities_cmd(client, message):
        await message.reply(
            "🎲 **QUIZ REWARD POOL**\n\n"
            f"{_format_rarity_list()}\n\n"
            "Owner can use `/setquizrarities NORMAL, MYTHICAL` or `/setquizrarities all`."
        )

    @app.on_message(filters.command("setquizrarities"))
    async def set_quiz_rarities_cmd(client, message):
        if not message.from_user or message.from_user.id != OWNER_ID:
            await message.reply("⛔ Owner only.")
            return
        raw = (message.text or "").split(maxsplit=1)
        if len(raw) < 2 or raw[1].strip().casefold() in {"all", "default", "reset"}:
            set_quiz_rarities([])
            await message.reply("✅ Quiz reward pool reset to all rarities with available characters.")
            return
        selected, invalid = _parse_rarity_names(raw[1])
        if invalid or not selected:
            available = ", ".join(get_character_rarities())
            await message.reply(f"❌ Unknown rarity: {', '.join(invalid) or 'none'}.\nAvailable: {available}")
            return
        set_quiz_rarities(selected)
        await message.reply(f"✅ Quiz reward rarities set to: {_format_rarity_list()}")

    @app.on_message(filters.command("addquizrarity"))
    async def add_quiz_rarity_cmd(client, message):
        if not message.from_user or message.from_user.id != OWNER_ID:
            await message.reply("⛔ Owner only.")
            return
        raw = (message.text or "").split(maxsplit=1)
        if len(raw) < 2:
            await message.reply("Usage: `/addquizrarity [rarity]`")
            return
        selected, invalid = _parse_rarity_names(raw[1])
        current = get_quiz_rarities()
        if invalid or not selected:
            await message.reply(f"❌ Unknown rarity: {', '.join(invalid) or raw[1]}")
            return
        set_quiz_rarities(current + [r for r in selected if r not in current])
        await message.reply(f"✅ Added to quiz pool: {_format_rarity_list()}")

    @app.on_message(filters.command("removequizrarity"))
    async def remove_quiz_rarity_cmd(client, message):
        if not message.from_user or message.from_user.id != OWNER_ID:
            await message.reply("⛔ Owner only.")
            return
        raw = (message.text or "").split(maxsplit=1)
        if len(raw) < 2:
            await message.reply("Usage: `/removequizrarity [rarity]`")
            return
        selected, invalid = _parse_rarity_names(raw[1])
        if invalid or not selected:
            await message.reply(f"❌ Unknown rarity: {', '.join(invalid) or raw[1]}")
            return
        current = [r for r in get_quiz_rarities() if r not in selected]
        set_quiz_rarities(current)
        await message.reply(f"✅ Removed. Current quiz pool: {_format_rarity_list()}")


async def handle_quiz_callback(client, callback):
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Invalid quiz button.", show_alert=True)
        return
    try:
        choice = int(parts[2])
    except ValueError:
        await callback.answer("Invalid answer.", show_alert=True)
        return
    quiz = ACTIVE_QUIZZES.get(callback.message.chat.id)
    if not quiz or quiz.get("token") != parts[1] or time.time() - quiz["created_at"] >= QUIZ_TIMEOUT:
        ACTIVE_QUIZZES.pop(callback.message.chat.id, None)
        await callback.answer("This quiz has expired.", show_alert=True)
        return
    if choice != quiz["correct"]:
        ACTIVE_QUIZZES.pop(callback.message.chat.id, None)
        await callback.answer("❌ Wrong answer! Quiz ended.", show_alert=True)
        try:
            await callback.message.edit_text(
                "❌ **QUIZ ENDED**\n\n"
                f"{callback.from_user.mention} selected the wrong answer.\n"
                "No character was spawned."
            )
        except Exception:
            await callback.message.edit_reply_markup(reply_markup=None)
        return
    ACTIVE_QUIZZES.pop(callback.message.chat.id, None)
    await callback.answer("✅ Correct!", show_alert=False)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await spawn_quiz_character(
        client,
        callback.message.chat.id,
        getattr(callback.message.chat, "title", None) or "Group",
    )
