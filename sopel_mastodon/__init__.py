"""
## Mastodon integration for Sopel IRC Bot

Currently expects to be used alongside as little other plugins/modules as possible. It (re)uses some short hand commands (e.g.: t, r, d)
"""
from base64 import b64encode
from mastodon import Mastodon, MastodonNotFoundError
from sopel import config, logger, plugin
from sopel.bot import Sopel, SopelWrapper
from sopel.trigger import Trigger
from sopel_mastodon.structures import LimitedSizeDict, strip_tags
import sopel_mastodon

PLUGIN_OUTPUT_PREFIX = "[Mastodon] "

LOGGER = logger.get_logger(__name__)

# TODO: move to config file:
NOTIFICATION_CHANNEL = "#hsmr-test"


@plugin.require_privilege(plugin.OP)
@plugin.require_chanmsg("Only available in Channel")
@plugin.command("toot", "t")
def normal_toot(bot: SopelWrapper, trigger: Trigger):
    message = trigger.args[1].split(" ", 1)[1]
    author = trigger.nick
    post = message + "\n~" + author
    toot(bot, post)


@plugin.require_privilege(plugin.OP)
@plugin.require_chanmsg("Only available in Channel")
@plugin.command("tootanon", "ta")
def anon_toot(bot: SopelWrapper, trigger: Trigger):
    message = trigger.args[1].split(" ", 1)[1]
    toot(bot, message, True)


@plugin.require_privilege(plugin.OP)
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
    messageCache = config.getReplyCache()
    if key not in messageCache:
        bot.say(PLUGIN_OUTPUT_PREFIX + f"Unknown reference: {key}")
        return
    try:
        client.status_delete(messageCache[key]["id"])
        del messageCache[key]
        bot.say(PLUGIN_OUTPUT_PREFIX + f"Deleted: {key}")
    except MastodonNotFoundError:
        bot.say(PLUGIN_OUTPUT_PREFIX + f"[{key}] cannot be deleted")


@plugin.interval(15)
def check_notifications(bot: SopelWrapper):
    config: MastodonSection = bot.settings.mastodon
    client = config.getMastodonClient()
    messageCache = config.getReplyCache()
    notifications = client.notifications(mentions_only=True)
    mentions = filter(lambda x: x["type"] == "mention", notifications)
    statuses = map(lambda x: x["status"], mentions)
    for status in statuses:
        key = tootEncoding(status)
        bot.say(
            PLUGIN_OUTPUT_PREFIX + f"Account: {status['account']['acct']}",
            NOTIFICATION_CHANNEL,
        )
        bot.say(
            PLUGIN_OUTPUT_PREFIX + f"{strip_tags(status['content'])}",
            NOTIFICATION_CHANNEL,
        )
        bot.say(
            PLUGIN_OUTPUT_PREFIX + f"Mention: [{key}] {status['url']}",
            NOTIFICATION_CHANNEL,
        )
        messageCache[key] = status
    client.notifications_clear()


def toot(
    bot: Sopel | SopelWrapper,
    post: str,
    sensitive: bool = False,
    reply: str | None = None,
):
    """
    Helper function to send/reply to a toot.\\
    Needs the Sopel or SopelWrapper object as bot since the Mastodon client is instanced in the bot settings
    """
    config: MastodonSection = bot.settings.mastodon
    client = config.getMastodonClient()
    messageCache = config.getReplyCache()
    if reply is None:
        LOGGER.info(f"Tooting: {post}")
        result = client.status_post(post, sensitive=sensitive)
    else:
        if reply not in messageCache:
            bot.say(PLUGIN_OUTPUT_PREFIX + f"Unknown reference to reply to: {reply}")
            return
        previous = messageCache[reply]
        LOGGER.info(f"Replying: {post} to: {previous['id']}")
        result = client.status_reply(previous, status=post, sensitive=sensitive)
    LOGGER.debug(f"Toot Result: {result}")
    key = tootEncoding(result)
    messageCache[key] = result
    bot.say(PLUGIN_OUTPUT_PREFIX + f"[{key}] {result['url']}")


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
            "Mastodon plugin is missing necessary config values. Plugin will not work"
        )
    section.initMastodon()
    # TODO: verify credentials?


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
    2. Stores state of the running plugin

    I don't like this, but I also don't know how to model this better atm.
    """

    id = config.types.ValidatedAttribute("id", str, is_secret=True)
    secret = config.types.ValidatedAttribute("secret", str, is_secret=True)
    token = config.types.ValidatedAttribute("token", str, is_secret=True)
    base_url = config.types.ValidatedAttribute("base_url", str)
    messageCacheLimit = config.types.ValidatedAttribute(
        "messageCacheLimit", int, default=50
    )

    mastodonClient: Mastodon
    messageCache: LimitedSizeDict

    def initMastodon(self) -> None:
        self.mastodonClient = Mastodon(self.id, self.secret, self.token, self.base_url)
        self.messageCache = LimitedSizeDict(size_limit=self.messageCacheLimit)

    def getMastodonClient(self) -> Mastodon:
        return self.mastodonClient

    def getReplyCache(self) -> LimitedSizeDict:
        return self.messageCache
