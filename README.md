# datmarket-websocket
An event driven network prototype to broadcast financial informations based on Tavendo frameworks and InfluxDB.

What is this? What it do ?
- Collect data from financial sources (i.e., Bitcoin exchanges, Yahoo Financial API, etc.)
- Broadcast real time events
- Render OHLC and broadcast them as soon as available
- Set up 'channels' over a WAMP realm, which could be subscribed by SaaS
