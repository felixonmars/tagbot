#!/usr/bin/env python2
from tagbot import TagHandler, Bot
import random

bot = Bot()
taghandler = TagHandler(bot.api)
taghandler.c.execute("SELECT user FROM tags WHERE tags != '[]'")
results = taghandler.c.fetchall()
randomresult = random.choice(results)
taghandler.get_tag(randomresult[0], None)
