# datmarket-websocket
An event driven decentralized network prototype to broadcast financial informations based on Tavendo frameworks and InfluxDB.

What is this? What it do ?
- Collect data from financial sources (i.e., Bitcoin exchanges, Yahoo Financial API, etc.)
- Broadcast real time events
- Render OHLC and broadcast them as soon as available
- Set up 'channels' over a WAMP realm, which could be subscribed by SaaS

Dependencies:

- Python 2.7
- Twisted 13.2.0
- Crossbar.io 0.10.1
- Autobahn|Python 0.9.5
- Autobahn|JS 0.9.4

Backend (DBMS, save broadcasted-over-the-network data to influxdb) and frontend (real2real proxy and JS clients events binder) main components are handled by Crossbar.io router, announcers (could be delocalizated) need valid credentials to join the network, as well as data managers like OHLC builders.

Json static files are handled and mantained by data managers for fast resuming.

TODO: ECDSA authenticator for broadcasters, custom authentication for clients.
