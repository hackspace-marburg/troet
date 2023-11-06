from base64 import b64encode
from time import sleep

from sopel import config, plugin
from sopel.bot import Sopel, SopelWrapper
from sopel.tools import get_logger
from sopel.trigger import Trigger

from collections import OrderedDict
from io import StringIO
from html.parser import HTMLParser

from sopel.tools import get_logger
from sopel.db import SopelDB

from threading import Thread, Event
from mastodon import Mastodon, MastodonNotFoundError, MastodonAPIError

PLUGIN_OUTPUT_PREFIX = "[troooet] "

LOGGER = get_logger(__name__)


class LimitedSizeDict(OrderedDict):
    """Dictionary with limited Size which also saves it's status in
    the SopelDB for persistency across restarts"""

    plugin_name = "troet"
    keylistkey = "lsdKeys"
    db: SopelDB

    def __init__(self, botDB: SopelDB, client: Mastodon, *args, **kwds):
        self.size_limit = kwds.pop("size_limit", None)
        self.db: SopelDB = botDB
        OrderedDict.__init__(self, *args, **kwds)
        # Check of keys are present in Database.
        keys = self.db.get_plugin_value(self.plugin_name, self.keylistkey)
        # LOGGER.info(f"Got Keys from DB: {keys}")
        if keys is not None:
            for key in keys:
                # Load Messages from old keys back into new dict
                value = self.db.get_plugin_value(self.plugin_name, key)
                try:
                    result = client.search_v2(value)
                    if result["statuses"]:
                        OrderedDict.__setitem__(self, key, result["statuses"][0])
                except MastodonAPIError as APIError:
                    LOGGER.warn(f"API didn't like {key} - {value} - {APIError}")

            # Updates dict in case more keys were loaded
            # or old keys could not be loaded from mastodon
            self._check_size_limit()

    def __setitem__(self, key, value):
        # Set's a new key, value pair in DB and dict. Aferwards checks limit
        self.db.set_plugin_value(self.plugin_name, key, value["url"])
        returnvalue = OrderedDict.__setitem__(self, key, value)
        self._check_size_limit()
        return returnvalue

    def __delitem__(self, key) -> None:
        # Deletes items. From Database and updates keylist in DB. Then from dict.
        self.db.delete_plugin_value(self.plugin_name, key)
        self.db.set_plugin_value(self.plugin_name, self.keylistkey, list(self.keys()))
        return super().__delitem__(key)

    def _check_size_limit(self):
        # Checks limit, removes entries which exceed limit and updates db keylist
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                key, _ = self.popitem(last=False)
                self.db.delete_plugin_value(self.plugin_name, key)
            self.db.set_plugin_value(
                self.plugin_name, self.keylistkey, list(self.keys())
            )


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()


@plugin.require_chanmsg("Only available in Channel")
@plugin.command("toot", "t")
def normal_toot(bot: SopelWrapper, trigger: Trigger):
    message = trigger.args[1].split(" ", 1)[1]
    author = trigger.nick
    post = message + "\n~" + author
    toot(bot, post)


@plugin.require_privilege(plugin.OP)
@plugin.require_chanmsg("Only available in Channel")
@plugin.command("listedtoot", "lt")
def listed_toot(bot: SopelWrapper, trigger: Trigger):
    message = trigger.args[1].split(" ", 1)[1]
    author = trigger.nick
    post = message + "\n~" + author
    toot(bot, post, visibility="public")


@plugin.require_privilege(plugin.OP)
@plugin.require_chanmsg("Only available in Channel")
@plugin.command("tootanon", "ta")
def anon_toot(bot: SopelWrapper, trigger: Trigger):
    message = trigger.args[1].split(" ", 1)[1]
    toot(bot, message, True)


@plugin.require_chanmsg("Only available in Channel")
@plugin.command("reply", "r")
def reply_toot(bot: SopelWrapper, trigger: Trigger):
    parameters = trigger.args[1].split(" ", 1)[1].split(" ", 1)
    author = trigger.nick
    post = parameters[1] + "\n~" + author
    toot(bot, post, reply=parameters[0])


@plugin.require_privilege(plugin.OP)
@plugin.require_chanmsg("Only available in Channel")
@plugin.command("replyanon", "ra")
def reply_anon_toot(bot: SopelWrapper, trigger: Trigger):
    parameters = trigger.args[1].split(" ", 1)[1].split(" ", 1)
    toot(bot, parameters[1], reply=parameters[0])


@plugin.require_privilege(plugin.OP)
@plugin.require_chanmsg("Only available in Channel")
@plugin.command("deletetoot", "d")
def delete_toot(bot: SopelWrapper, trigger: Trigger):
    key = trigger.args[1].split(" ", 1)[1]
    config: MastodonSection = bot.settings.mastodon
    client = config.getMastodonClient()
    messageCache = config.getMessageCache()
    if key not in messageCache:
        bot.notice(PLUGIN_OUTPUT_PREFIX + f"Unknown reference: {key}")
        return
    try:
        client.status_delete(messageCache[key]["id"])
        del messageCache[key]
        bot.notice(PLUGIN_OUTPUT_PREFIX + f"Deleted: {key}")
    except MastodonNotFoundError:
        bot.notice(PLUGIN_OUTPUT_PREFIX + f"[{key}] cannot be deleted")


@plugin.require_chanmsg("Only available in Channel")
@plugin.command("search", "s")
def search(bot: SopelWrapper, trigger: Trigger):
    config: MastodonSection = bot.settings.mastodon
    client = config.getMastodonClient()
    query = trigger.args[1].split(" ", 1)[1]
    result = client.search_v2(query)
    if not result["statuses"]:
        bot.notice(PLUGIN_OUTPUT_PREFIX + "No status found. Did you use a permalink?")
        return
    status = result["statuses"][0]
    print_toot(status, bot, trigger.sender)


@plugin.require_chanmsg("Only available in Channel")
@plugin.command("mute", "m")
def mute(bot: SopelWrapper, trigger: Trigger):
    config: MastodonSection = bot.settings.mastodon
    client = config.getMastodonClient()
    parameter = trigger.args[1].split(" ", 1)[1]
    messageCache = config.getMessageCache()
    key: str
    if parameter in messageCache:
        key = parameter
        toot = messageCache[key]
    else:
        result = client.search_v2(parameter)
        if not result["statuses"]:
            bot.notice(PLUGIN_OUTPUT_PREFIX + "No status found. Nothing muted.")
            return
        toot = result["statuses"][0]
        key = tootEncoding(toot)
        messageCache[key] = toot
    status = client.status_mute(toot)
    if not status:
        bot.notice(PLUGIN_OUTPUT_PREFIX + f"[{key}] No reply on request to mute.")
        return
    if status["muted"]:
        bot.notice(PLUGIN_OUTPUT_PREFIX + f"[{key}] Muted.")
    else:
        bot.notice(PLUGIN_OUTPUT_PREFIX + f"[{key}] Failed to mute.")


@plugin.command("fav")
@plugin.require_chanmsg("Only available in Channel")
def fav(bot: SopelWrapper, trigger: Trigger):
    key = trigger.args[1].split(" ", 1)[1]
    config: MastodonSection = bot.settings.mastodon
    client = config.getMastodonClient()
    messageCache = config.getMessageCache()
    if key not in messageCache:
        bot.notice(PLUGIN_OUTPUT_PREFIX + f"Unknown reference: {key}")
        return
    if not messageCache[key]["favourited"]:
        toot = client.status_favourite(messageCache[key]["id"])
        bot.notice(
            PLUGIN_OUTPUT_PREFIX + f"Favourited: [{key}] {messageCache[key]['url']}"
        )
    else:
        toot = client.status_unfavourite(messageCache[key]["id"])
        bot.notice(
            PLUGIN_OUTPUT_PREFIX + f"Unfavourited: [{key}] {messageCache[key]['url']}"
        )
    messageCache[key] = toot


@plugin.command("cancel")
@plugin.require_chanmsg("Only available in Channel")
@plugin.require_privilege(plugin.OP)
def cancel(bot: SopelWrapper, trigger: Trigger):
    config: MastodonSection = bot.settings.mastodon
    if config.delayed_tooting == True:
        [x.set() for x in config.delayed_toots]
        bot.notice(PLUGIN_OUTPUT_PREFIX + "Cancelled all floating toots.")
    else:
        bot.notice(
            PLUGIN_OUTPUT_PREFIX + "Delayed tooting not enabled. This does nothing."
        )


@plugin.interval(30)
def check_notifications(bot: Sopel):
    """Checks every 30 seconds for new notifications from Mastodon,
    prints them and makes them available to reply to
    """
    config: MastodonSection = bot.settings.mastodon
    if config.notification_channel is None:
        return
    client = config.getMastodonClient()

    # Get Notifications, extract statuses and print them
    notifications = client.notifications(mentions_only=True)
    mentions = filter(lambda x: x["type"] == "mention", notifications)
    statuses = map(lambda x: x["status"], mentions)
    for status in statuses:
        print_toot(status, bot, config.notification_channel)

    # if there were notifications clear them
    if notifications:
        client.notifications_clear()


def print_toot(status, bot: Sopel | SopelWrapper, recipient):
    """Outputs a full status to IRC and adds it to the messageCache"""
    config: MastodonSection = bot.settings.mastodon
    messageCache = config.getMessageCache()
    key = tootEncoding(status)
    bot.notice(
        PLUGIN_OUTPUT_PREFIX
        + f"By: {status['account']['acct']} At: {status['created_at']}",
        recipient,
    )
    bot.notice(
        PLUGIN_OUTPUT_PREFIX + f"{strip_tags(status['content'])}",
        recipient,
    )
    # For all images attached to the toot provide a link
    # These links are long. Maybe shorten in the future?
    # Observation: Media links of restricted toots are NOT restricted. So this always works.
    for media in status["media_attachments"]:
        bot.notice(PLUGIN_OUTPUT_PREFIX + "Media: " + media["url"], recipient)
    bot.notice(
        PLUGIN_OUTPUT_PREFIX + f"[{key}] {status['url']}",
        recipient,
    )
    messageCache[key] = status


def toot(
    bot: SopelWrapper,
    post: str,
    sensitive: bool = False,
    reply: str | None = None,
    visibility: str = "unlisted",
):
    """Helper function to send/reply to a toot.\\
    Needs the SopelWrapper object as bot since the Mastodon client is instanced in the bot settings
    """
    config: MastodonSection = bot.settings.mastodon
    client = config.getMastodonClient()
    messageCache = config.getMessageCache()

    def send_toot(**kwargs):
        result = client.status_post(**kwargs)
        LOGGER.debug(f"Toot Result: {result}")
        key = tootEncoding(result)
        messageCache[key] = result
        bot.notice(PLUGIN_OUTPUT_PREFIX + f"[{key}] {result['url']}")

    def post_status(**kwargs):
        if config.delayed_tooting == True:
            bot.notice(
                PLUGIN_OUTPUT_PREFIX
                + f"Toot delayed. Cancel all unposted toots with .cancel"
            )
            evt = Event()
            config.delayed_toots.append(evt)

            def post_eventually(event: Event):
                sleep(config.delay)
                if not event.is_set():
                    send_toot(**kwargs)
                config.delayed_toots.remove(event)

            thread = Thread(target=post_eventually, args=(evt,))
            thread.run()
        else:
            send_toot(**kwargs)

    if reply is None:
        LOGGER.info(f"Tooting: {post}")
        post_status(status=post, sensitive=sensitive, visibility=visibility)
    else:
        if reply not in messageCache:
            bot.notice(PLUGIN_OUTPUT_PREFIX + f"Unknown reference to reply to: {reply}")
            return
        previous = messageCache[reply]
        LOGGER.info(f"Replying: {post} to: {previous['id']}")
        post_status(
            in_reply_to_id=previous,
            status=post,
            sensitive=sensitive,
            visibility=visibility,
        )


def tootEncoding(toot):
    if "id" not in toot:
        raise ValueError("Tried to hash a non-toot!")
    return b64encode((hash(toot["id"]) & 0xFFFFFF).to_bytes(3, byteorder="big")).decode(
        "utf-8"
    )


def setup(bot: Sopel):
    """
    Setup function is called by Sopel after module initialization, before connection to IRC network.\\
    Initializes the Mastodon class. But: Connection will only be established on Mastodon api calls.
    """
    bot.settings.define_section("mastodon", MastodonSection)
    section: MastodonSection = bot.settings.mastodon
    if (
        section.id is None
        or section.secret is None
        or section.token is None
        or section.base_url is None
    ):
        LOGGER.error(
            "Mastodon plugin is missing necessary config values. Plugin will not work."
        )
    section.initMastodon(bot)
    # TODO: verify credentials?
    # But: section.getMastodonClient().app_verify_credentials() does not seem to work for this.


def configure(config: config.Config):
    config.define_section("mastodon", MastodonSection)
    config.mastodon.configure_setting("id", "What's your Mastodon clinet ID?")
    config.mastodon.configure_setting("secret", "What's your Mastodon client secret?")
    config.mastodon.configure_setting("token", "What's your Mastodon access token?")
    config.mastodon.configure_setting(
        "base_url", "What's your Mastodon instance base url?"
    )


class MastodonSection(config.types.StaticSection):
    """
    The Mastodon config section class serves two purposes:
    1. Defines the config fields expected in the Sopel config file
    2. Stores state of the running plugin (Mastodon client and messageCache)

    I don't like this, but I also don't know how to model this better right now.
    """

    id = config.types.ValidatedAttribute("id", str, is_secret=True)
    secret = config.types.ValidatedAttribute("secret", str, is_secret=True)
    token = config.types.ValidatedAttribute("token", str, is_secret=True)
    base_url = config.types.ValidatedAttribute("base_url", str)
    messageCacheLimit = config.types.ValidatedAttribute(
        "messageCacheLimit", int, default=50
    )
    notification_channel = config.types.ValidatedAttribute("notification_channel", str)
    delayed_tooting = config.types.ValidatedAttribute("delayed", bool, default=False)
    delay = config.types.ValidatedAttribute("delay", int, default=360)
    delayed_toots: list[Event] = list()

    mastodonClient: Mastodon
    messageCache: LimitedSizeDict

    def initMastodon(self, bot) -> None:
        self.mastodonClient = Mastodon(self.id, self.secret, self.token, self.base_url)
        self.messageCache = LimitedSizeDict(
            size_limit=self.messageCacheLimit, botDB=bot.db, client=self.mastodonClient
        )
        nc = str(self.notification_channel)
        self.notification_channel = nc.strip('"')

    def getMastodonClient(self) -> Mastodon:
        return self.mastodonClient

    def getMessageCache(self) -> LimitedSizeDict:
        return self.messageCache
