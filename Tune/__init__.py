# Authored By Certified Coders © 2025
from Tune.core.bot import MusicBotClient
from Tune.core.dir import StorageManager
from Tune.core.git import git
from Tune.core.userbot import Userbot
from Tune.misc import dbb, heroku
from Tune.logging import LOGGER

StorageManager()
git()
dbb()
heroku()

app = MusicBotClient()
userbot = Userbot()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
