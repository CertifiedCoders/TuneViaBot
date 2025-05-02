from Tune.core.bot import JARVIS
from Tune.core.dir import dirr
from Tune.core.git import git
from Tune.core.userbot import Userbot
from Tune.misc import dbb, heroku
from Tune.logging import LOGGER

dirr()
git()
dbb()
heroku()

app = JARVIS()
userbot = Userbot()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()
