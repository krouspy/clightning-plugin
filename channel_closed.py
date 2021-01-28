#!/usr/bin/env python3
from pyln.client import Plugin

plugin = Plugin()


@plugin.subscribe("channel_state_changed")
def on_channel_closed(plugin, channel_state_changed, **kwargs):
    new_state = channel_state_changed["new_state"]
    if new_state == 'CLOSINGD_COMPLETE':
        plugin.log("channel {channel_id} has closed - cause: {cause}".format(**channel_state_changed))


plugin.run()