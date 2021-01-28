#!/usr/bin/env python3
from pyln.client import Plugin

plugin = Plugin()


@plugin.hook("htlc_accepted")
def on_channel_closed(onion, htlc, plugin, **kwargs):
    plugin.log('htlc accepted!')
    return {'result': 'continue'}


plugin.run()