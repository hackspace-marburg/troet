# Sopel Mastodon

Mastodon plugin for [Sopel](https://sopel.chat/) IRC bots.

## Installation

You must already have Sopel installed to use this method.
```
git clone https://github.com/hackspace-marburg/sopel-mastodon
cd sopel-mastodon
pip install .
```
As soon as this is some kind of release ready this should work: `pip install sopel_modules.mastodon` (but it does not right now as this is very early stage software)

## Limitations

This is not a general purpose Mastodon client. The intetion was to make interaction between an IRC Channel and Mastodon possible to:

- Toot
- Be notified and reply to mentions
- Delete things others (drunkenly) tooted earlier
- Reply to specific toots (complicated, but also rarest intended use case)

As such you can only react / reply based on toots the bot has already seen. This removes the necessity for users to enter global toot/status id's for reactions. To make this easier each toot sent or recieved is assigned a 4 character code by which it will be refered to by the bot. This code is only meaningful for the bot and is **not** taken from the Mastodon network.

## Commands

``` .toot .t ```

Send a toot! Whatever is entered after the command is tooted. At the end a newline and the Username of the sending user will be attached. On success returns the bot code of the toot as well as a permalink to it.

``` .tootanon .ta ```

Does the same as `.toot` but without attaching the username.

``` .reply .r ```

The first word after the command is the bot code of the toot to reply to.

``` .replyanon .ra ```

Relates to reply as tootanon relates to toot.

``` .delete .d ```

Given the bot code of the toot it will try to delete the toot. Only works on toots sent from this account, others will obviously fail.

``` .search .s ```

If given a permalink to a toot it will show this toot in IRC and assign a bot code to it. Afterwards the bot can be used to reply to it.
In the Mastodon UI you can get the permalink of a toot by clicking on the timestamp. If it contains `/web/` it is **not** the permalink.

## TODOs

- write proper Readme.md
- Enable ability to fav a toot
- Media posts should upload the media somewhere else and link to them
- Handle long messages (split into several toots)
- Move messageCache to Database
- Clarify with "Team"
  - How should Notifications be displayed?
  - Which users should have toot/anonymous/delete-permission?
- At the moment this code painfully ignores any kind of ratelimiting
  - Should not be a problem for expected use. 
- Unittests