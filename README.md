### Overview

The objective here is to write a plugin on [clightning](https://github.com/ElementsProject/lightning). I decomposed the work into two sections, the first section describes the setup of the environment, from building clightning to fund a channel; and the second section focuses on writing a plugin in python.

### Environment

Ubuntu 20.04 x64bit

### Setup

The installation is very well explained in the [documentation](https://github.com/ElementsProject/lightning/blob/master/doc/INSTALL.md).

We will build clightning directly from source code.

```
$ sudo apt-get update
$ sudo apt-get install -y \
  autoconf automake build-essential git libtool libgmp-dev \
  libsqlite3-dev python3 python3-mako net-tools zlib1g-dev libsodium-dev \
  gettext
# Install bitcoin-core
$ sudo apt-get install snapd
$ sudo snap install bitcoin-core
$ sudo ln -s /snap/bitcoin-core/current/bin/bitcoin{d,-cli} /usr/local/bin/
```

Get source code

```
$ git clone https://github.com/ElementsProject/lightning
```

Install development dependencies

```
$ sudo apt-get install -y valgrind python3-pip libpq-dev
$ cd lightning
$ sudo pip3 install -r requirements.txt
```

Then we can build clightning

```
$ ./configure --enable-developer
$ make
$ sudo make install
```

The Lightning Network is built on top of the Bitcoin blockchain so we first need to have a bitcoin node and specify clightning to connect to the node. For development, we have the choice between the bitcoin `testnet` or to use our own bitcoin network, a `regtest`. The regtest would be a better choice since it allows us to have full control over the network and we don't need to bother to sync the testnet.

The `clightning` repository provides a script to bootstrap a regtest network at `contrib/startup_regtest`. But before launching the script, we will first create a config file for bitcoind.

```
# ~/.bitcoin/bitcoin.conf
daemon=1
regtest=1
server=1 # Listen to JSON-RPC commands

fallbackfee=0.00000253

# need to set feerate
rpcuser=admin
rpcpassword=admin
```

Sourcing the script with `. contrib/startup_regtest.sh` update the script and `start_ln` will launch bitcoind along with two lightning nodes.
If no bitcoin wallet has been previously loaded, an error will pop out asking to create or load a wallet.

```
$ bt-cli createwallet btc-wallet
$ bt-cli getnewaddress
> bcrt1qkna5qv72w99cz4tk2ec2596jn0eq4s2akzr47y
$ bt-cli generatetoaddress 101 bcrt1q55zd3v65uyssf40ja6070g249n8avf9qmh2etv
> [...]
$ bt-cli getbalance
> 50.00000000
```

Now everything is set up correctly and we can start doing things on clightning like opening and funding a channel between our two lightning nodes. `start_ln` provides 6 aliases to interact with our 3 nodes.

```
$ start_ln
> Commands:
    l1-cli, l1-log,
    l2-cli, l2-log,
    bt-cli, stop_ln
```

Fund node

```
$ l1-cli newaddr
{
   "address": "bcrt1qqyek8j0mnfnhup2r6h6mkv0m9267n5c2aavrk2",
   "bech32": "bcrt1qqyek8j0mnfnhup2r6h6mkv0m9267n5c2aavrk2"
}

$ bt-cli sendtoaddress bcrt1qqyek8j0mnfnhup2r6h6mkv0m9267n5c2aavrk2 10
> 23d2b9ea75a161b0db4e4dd2ebc0dec6e8c925dc1e5198d64f528d4d9cff3b01

# mine one block to process transaction
$ bt-cli generatetoaddress 1 bcrt1qkna5qv72w99cz4tk2ec2596jn0eq4s2akzr47y

$ l1-cli listfunds
{
   "outputs": [
      {
         "txid": "23d2b9ea75a161b0db4e4dd2ebc0dec6e8c925dc1e5198d64f528d4d9cff3b01",
         "output": 0,
         "value": 1000000000,
         "amount_msat": "1000000000000msat",
         "scriptpubkey": "0014013363c9fb9a677e0543d5f5bb31fb2ab5e9d30a",
         "address": "bcrt1qqyek8j0mnfnhup2r6h6mkv0m9267n5c2aavrk2",
         "status": "confirmed",
         "blockheight": 102,
         "reserved": false
      }
   ],
   "channels": []
}
```

Connect our lightning nodes

```
$ l2-cli getinfo
{
   "id": "02320661c51f0ccab5182ab616986db08a18a7e4c65e17be80053f1fe4953fd054",
   "alias": "LOUDMONKEY-v0.9.3-13-g6bed85b",
   "color": "023206",
   "num_peers": 0,
   "num_pending_channels": 0,
   "num_active_channels": 0,
   "num_inactive_channels": 0,
   "address": [],
   "binding": [
      {
         "type": "ipv4",
         "address": "127.0.0.1",
         "port": 7272
      }
   ],
   "version": "v0.9.3-13-g6bed85b",
   "blockheight": 102,
   "network": "regtest",
   "msatoshi_fees_collected": 0,
   "fees_collected_msat": "0msat",
   "lightning-dir": "/tmp/l2-regtest/regtest"
}

$ l1-cli connect 02320661c51f0ccab5182ab616986db08a18a7e4c65e17be80053f1fe4953fd054 localhost 7272
{
   "id": "02320661c51f0ccab5182ab616986db08a18a7e4c65e17be80053f1fe4953fd054",
   "features": "02aaa2"
}
```

When funding our channel we will run into the following error

```
$ l1-cli fundchannel 02320661c51f0ccab5182ab616986db08a18a7e4c65e17be80053f1fe4953fd054 100000000msat
{
   "code": -1,
   "message": "Cannot estimate fees"
}
```

And when estimating bitcoin fee we will see the following

```
$ bt-cli estimatesmartfee 2
{
  "errors": [
    "Insufficient data or no feerate found"
  ],
  "blocks": 0
}
```

As mentioned in this [issue](https://github.com/bitcoin/bitcoin/issues/11500), this is because not enough blocks have been mined. So we can either mined blocks manually or use a script.

```
$ mkdir -p ~/update-fees/src
$ cd ~/update-fees
$ yarn init -y
$ yarn add bitcoin-core
$ nvim src/app.js
```

Then paste the following, it will generate blocks containing transactions and fees.

```javascript
// ~/update-fees/src/app.js
const Client = require("bitcoin-core");

const bitcoind = new Client({
  port: "18443",
  host: "localhost",
  network: "regtest",
  username: "admin",
  password: "admin",
});

(async function () {
  for (let i = 0; i < 2; i++) {
    console.log("i", i);
    for (let j = 0; j <= 10; j++) {
      console.log("j", j);
      const newAddress = await bitcoind.getNewAddress();
      const unfundedTx = await bitcoind.createRawTransaction([], {
        [newAddress]: "0.005",
      });
      const randFee =
        0.00001 * Math.pow(1.1892, Math.floor(Math.random() * 29));
      const fundedTx = await bitcoind.fundRawTransaction(unfundedTx, {
        feeRate: randFee.toFixed(8).toString(),
      });
      const signedTx = await bitcoind.signRawTransactionWithWallet(
        fundedTx.hex
      );
      const sentTx = await bitcoind.sendRawTransaction(signedTx.hex);
    }
    await bitcoind.generateToAddress(1, "mp76nrashrCCYLy3a8cAc5HufEas11yHbh");
  }
})();
```

```
$ node src/app.js
```

Then we can check again if the fee rate has updated.

**Note** that if the error is still here, just run multiple times the script.

```
$ bt-cli estimatesmartfee 2
{
  "feerate": 0.00022625,
  "blocks": 2
}
```

Now we can fund our channel

```
$ l1-cli fundchannel 02320661c51f0ccab5182ab616986db08a18a7e4c65e17be80053f1fe4953fd054 100000000msat
{
   "tx": "02000000000101013bff9c4d8d524fd698511edc25c9e8c6dec0ebd24d4edbb061a175eab9d2230000000000fdffffff02a08601000000000022002028c379bb53c58b0f034e4d8fa8d401580e7deb29adb4736edd4303c30d697523613f993b00000000160014a1de7adb2617642176df07664534f9804f5b7d110247304402200580ce08c1f2d2d943d2bf0e7eeb0f37a90eb3ed3be4e3afaddf68afe225e6e5022056ac51e0d529749b6be4218be579559283f44025910fc6d0a93d704337544e61012102f4c568d9835ffc91ca97b5065d03a3f2f9b2b12d3dacf6374a0e6c765681a3d86e000000",
   "txid": "9dd2873a6498eb93b3cddcbc0d69d56c4d58b3f90cc9ec578e208d0022878e8e",
   "channel_id": "8e8e8722008d208e57ecc90cf9b3584d6cd5690dbcdccdb393eb98643a87d29d",
   "outnum": 0
}

# mine some blocks to lock funds
$ bt-cli generatetoaddress 10 bcrt1qkna5qv72w99cz4tk2ec2596jn0eq4s2akzr47y

# check if everything is going fine
$ l1-cli listpeers
...
$ l1-cli listchannels
...
```

### Plugins

Regarding the python environment, the documentation is available [here](https://github.com/lightningd/plugins) and [here](https://lightning.readthedocs.io/PLUGINS.html) for the clightning plugin API.

We need to set the PYTHONPATH environment variable.

```
# ~/.bashrc
...
export PYTHONPATH=/home/ubuntu/lightning/contrib/pyln-client
```

Also, we need to tell clightning where to load our plugins. Python plugins are written outside the clightning repository and we specify their path through the flag `-plugin` to reference a single plugin or the flag `-plugin-dir` to reference a directory containing plugins.

In my case, I will give a try to this [issue](https://github.com/ElementsProject/lightning/issues/3662) so two plugins.

**DISCLAIMER**: For this issue, plugins have to be written in C and not Python in order for them to communicate with other plugins. So here, it serves only as an example but the pattern described here is good to follow if writting python plugins.

```
$ mkdir ~/plugins
$ cd ~/plugins
```

#### Channel closed

As we can see in the documentation, the event we should use is `channel_state_changed`. It allows us to be notified when the channel state changes and to see the `new_state` as well as the `cause`.

The plugin looks like this one.

```python
# ~/plugins/channel_closed.py

#!/usr/bin/env python3
from pyln.client import Plugin

plugin = Plugin()

@plugin.subscribe("channel_state_changed")
def on_channel_state_change(plugin, channel_state_changed, **kwargs):
    plugin.log("channel {channel_id} changed from {old_state} to {new_state} - cause: {cause}".format(**channel_state_changed))

plugin.run()
```

We can check values returned by simply telling lightningd to load the plugin and restarting our nodes.

For simplicity, I will modify the `start_nodes()` function in `startup_regtest.sh` script to auto add the `-plugin-dir` flag to the lightningd config file.

```sh
# ~/lightning/contrib/startup_regtest.sh
...

start_nodes() {
    ...
        for i in $(seq $node_count); do
            ...
            plugin-dir=/home/ubuntu/plugins
            ...
        done
    ...
}

...
```

Source again `startup_regtest.sh` to take changes into account

```
$ . ~/lightning/contrib/startup_regtest.sh
```

Then restart nodes

```
$ stop_ln
$ start_ln
```

Close channel to catch the event

```
$ l1-cli close 02320661c51f0ccab5182ab616986db08a18a7e4c65e17be80053f1fe4953fd054
$ l1-log
> INFO    plugin-channel_closed_notification.py: channel 8e8e8722008d208e57ecc90cf9b3584d6cd5690dbcdccdb393eb98643a87d29d changed from CLOSINGD_SIGEXCHANGE to CLOSINGD_COMPLETE - cause: user
```

So we can see that the value corresponding to a channel closed is `new_state=CLOSINGD_COMPLETE`. Therefore, we can update the our plugin as follow.

```python
# ~/plugins/channel_closed.py

#!/usr/bin/env python3
from pyln.client import Plugin

plugin = Plugin()


@plugin.subscribe("channel_state_changed")
def on_channel_closed(plugin, channel_state_changed, **kwargs):
    new_state = channel_state_changed["new_state"]
    if new_state == 'CLOSINGD_COMPLETE':
        plugin.log("channel {channel_id} has closed - cause: {cause}".format(**channel_state_changed))


plugin.run()
```

Then restart nodes

```
$ stop_ln
$ start_ln
```

Now we get notified (in the logs) each time a channel closes!

#### HTLC accepted

Writing this plugin is almost the same as the previous, the only difference is that we use a hook.

The hook we should use is [htlc_accepted](https://lightning.readthedocs.io/PLUGINS.html#htlc-accepted).

```python
# ~/plugins/htlc_accepted.py

#!/usr/bin/env python3
from pyln.client import Plugin

plugin = Plugin()


@plugin.hook("htlc_accepted")
def on_channel_closed(onion, htlc, plugin, **kwargs):
    plugin.log('htlc accepted!')
    return {'result': 'continue'}


plugin.run()
```

We are now notified (in the logs) each time a HTLC is accepted.

Note that these two plugins do not resolve the issue since the issue requires a more 'deep' solution.
