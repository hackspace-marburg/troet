from collections import OrderedDict
from io import StringIO
from html.parser import HTMLParser
from mastodon import Mastodon

from sopel.db import SopelDB


class LimitedSizeDict(OrderedDict):
    """Dictionary with limited Size which also saves it's status in
    the SopelDB for persistency across restarts"""

    plugin_name = "mastodon"
    keylistkey = "lsdKeys"
    db: SopelDB

    def __init__(self, botDB: SopelDB, client: Mastodon, *args, **kwds):
        self.size_limit = kwds.pop("size_limit", None)
        self.db: SopelDB = botDB
        OrderedDict.__init__(self, *args, **kwds)
        # Check of keys are present in Database.
        keys = self.db.get_plugin_value(self.plugin_name, self.keylistkey)
        print(f"Got Keys from DB: {keys}")
        if keys is not None:
            for key in keys:
                # Load Messages from old keys back into new dict
                value = self.db.get_plugin_value(self.plugin_name, key)
                result = client.search_v2(value)
                if result["statuses"]:
                    OrderedDict.__setitem__(self, key, result["statuses"][0])
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
