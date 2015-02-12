# datmarket-websocket
An event driven decentralized network prototype to broadcast financial informations.

What is this? What it does ?
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

To be done ASAP: ECDSA authenticator for broadcasters, custom authentication for clients.
Next step: Different wamp routers have to be able to talk each other and replicate informations across the network.

How to contribute? 
- Write your own announcer, for a service you would be see as advertised on the network.
- Do unit tests of the already existing code.
- Report the many bugs you will encounter :-)
