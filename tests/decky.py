import logging, os
logger = logging.getLogger("decky")
logging.basicConfig(level=logging.CRITICAL)
DECKY_USER_HOME = os.environ.get("TEST_HOME", "/home/deck")
DECKY_HOME = "/home/deck/homebrew"
DECKY_PLUGIN_SETTINGS_DIR = os.environ.get("TEST_SETTINGS", "/tmp/settings")
DECKY_PLUGIN_DIR = "/x"
DECKY_PLUGIN_RUNTIME_DIR = "/tmp/rt"
DECKY_PLUGIN_LOG_DIR = "/tmp/log"
async def emit(*a, **k): pass
