# Sopel Mastodon

Mastodon plugin for [Sopel](https://sopel.chat/) IRC bots.

## Installation

You must already have Sopel installed to use this method.
```
git clone https://github.com/sopel-irc/sopel-github
cd sopel-github
pip install .
```
As soon as this is some kind of release ready this should work: `pip install sopel_modules.mastodon` (but it does not right now)


## TODOs

- write proper Readme.md
- reply to toots which are not found via mention system
  - might involve "importing" toots based on link/id
  - link importing could become dangerous
- Check possibillity of:
  - Config/User changable delays for notification updates
- Clarify with "Team"
  - How should Notifications be displayed?
  - Which users should have toot/anonymous/delete-permission?
- At the moment this code painfully ignores any kind of ratelimiting
  - Should not be a problem for expected use. 
