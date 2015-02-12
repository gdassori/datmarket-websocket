from autobahn.twisted.wamp import ApplicationSessionFactory, WampWebSocketClientFactory
from twisted.internet.endpoints import clientFromString
from twisted.internet import reactor
from twisted.web.client import getPage
from autobahn.wamp import types
import json
from autobahn.wamp.exception import TransportLost
from wamp import wampClient
from time import time, strftime

class Cb():
    def __init__(self):
        self.cli = None
    def _set_cli(self, client):
        self.cli = client

class Announcer():
    def __init__(self):
        self.channels = {'btce': ['btcusd', 'btceur'], 'trt': ['btceur'], 'bitstamp': ['btcusd']}
        self.cb = Cb()
        self.onEvents = {"join": self.onJoin, "close": self.onClose}
        self.ticker = {}
        self.latestFetchedTrade = {}
        self.latestPublishedTickers = {}
        self.initWamp()

    def initWamp(self):
        def tryToConnect():
            print "trying to connect" if self.wamp_connection_retry == 0 else \
                "trying to connect (retry {})".format(self.wamp_connection_retry)
            self.wampClient = clientFromString(reactor, "tcp:127.0.0.1:8080")
            self.wampClient.connect(self.client_transport_factory)
            reactor.callLater(self.wamp_connection_timeout, isConnected)
        def isConnected():
            if not self.isOnline and self.wamp_connection_retry < self.wamp_max_retries:
                print "timeout ({}s) hit, retrying".format(self.wamp_connection_timeout)
                tryToConnect()
                self.wamp_connection_retry += 1
            elif not self.isOnline and self.wamp_connection_retry > self.wamp_max_retries:
                print "max retries hit, exiting"
                reactor.stop()
            elif self.isOnline:
                self.wamp_connection_retry = 0
        self.isOnline = False
        self.wamp_connection_retry = 0
        self.wamp_max_retries = 99
        self.wamp_connection_timeout = 10
        self.client_component_config = types.ComponentConfig(realm = u"datmarket0")
        self.client_factory = ApplicationSessionFactory(config = self.client_component_config)
        self.client_factory.session = lambda : wampClient(self.cb, self.client_component_config, self.onEvents)
        self.client_transport_factory = WampWebSocketClientFactory(self.client_factory.session,
                                                                   url="ws://localhost:8080/ws",
                                                                   debug = True,
                                                                   debug_wamp = True)
        tryToConnect()

    def unhandledError(self, data):
        print 'unhandled error: {}'.format(data)

    def onJoin(self):
        self.isOnline = True
        self.fetchBitstampTrades(bootstrap=True)
        self.fetchBTCETrades(bootstrap=True)
        self.fetchTRTTrades(bootstrap=True)

    def onClose(self, wasClean):
        print "on close invoked"
        self.isOnline = False
        if not wasClean:
            print "and wasnt a clean closing, reconnection"
            def reconnection():
                print "reinitializing wamp"
                self.initWamp()
                print "reconnecting"
                self.wampClient.connect(self.client_transport_factory)
            reactor.callLater(2, reconnection)

    def publishTicker(self, provider, data):
            self.cb.cli.publish("dm.tickers.{}".format(provider), data)
            self.latestPublishedTickers[provider] = data
            print "{} | published dm.tickers.{}: {}".format(strftime("%c"), provider, data)


    ######################### trades ###########################

    def __fetchedTrades(self, provider, res, bootstrap=False):
        res.reverse()
        newTrades = 0
        self.ticker[provider] = []
        for i, v in enumerate(res):
            if 'bitstamp' in provider:
                trade = {'amount':v['amount'], 'timestamp':v['date'], 'price': v['price'], 'id': v['tid']}
            elif 'trt' in provider:
                trade = {'amount':float(v['amount']), 'date':v['date'], 'price': float(v['price']), 'id': v['tid']}
            elif 'btce' in provider:
                trade = {'amount': v['amount'], 'timestamp': v['timestamp'], 'price': v['price'], 'id': v['tid']}
            exist = self.latestFetchedTrade.has_key(provider)
            if not exist or res[i]['tid'] not in self.latestFetchedTrade[provider]:
                if not exist:
                    self.latestFetchedTrade[provider] = []
                self.latestFetchedTrade[provider].insert(0, res[i]['tid'])
                self.latestFetchedTrade[provider] = self.latestFetchedTrade[provider][:1000]
                self.ticker[provider] = [res[i]['price'], int(time())]
                newTrades += 1
                if not bootstrap:
                    self.cb.cli.publish('dm.trades.{}'.format(provider), trade)
        if self.ticker[provider]:
            print "{} | published dm.tickers.{}: {}".format(strftime("%c"), provider, self.ticker[provider])
            self.publishTicker(provider, self.ticker[provider][0])
        if newTrades: print 'fetched {} new trade(s) for {}'.format(newTrades, provider)

    def fetchBitstampTrades(self, bootstrap=False):
        """
        single currency API
        """
        def _cb(res):
            try:
                res = json.loads(res)
                if res:
                    self.__fetchedTrades('bitstamp.btcusd', res, bootstrap=bootstrap)
                reactor.callLater(2, self.fetchBitstampTrades)
            except Exception as e:
                self.unhandledError(e)
                reactor.callLater(900 if "blocked" in res else 5, self.fetchBitstampTrades)
                if "blocked" in res: print "bitstamp API block hit, sleeping 900s"
        def _eb(e):
            self.unhandledError(e)
            reactor.callLater(5, self.fetchBitstampTrades)
        d = getPage('https://www.bitstamp.net/api/transactions?time=minute',
                timeout=20,
                headers={'Accept': 'application/json'})
        d.addCallbacks(_cb,  _eb)

    def fetchBTCETrades(self, bootstrap=False):
        """
        multiple currencies API
        """
        def _cb(res):
            btce_pairs = {'btcusd': 'btc_usd', 'btceur': 'btc_eur'}
            try:
                for pair in self.channels['btce']:
                    res_pair = json.loads(res)[btce_pairs[pair]]
                    if res_pair:
                        self.__fetchedTrades('btce.{}'.format(pair), res_pair, bootstrap=bootstrap)
                reactor.callLater(1, self.fetchBTCETrades)
            except Exception as e:
                self.unhandledError(e)
                reactor.callLater(5, self.fetchBTCETrades)
        def _eb(e):
            self.unhandledError(e)
            reactor.callLater(5, self.fetchBTCETrades)
        d = getPage('https://btc-e.com/api/3/trades/btc_usd-btc_eur',
                timeout=20,
                headers={'Accept': 'application/json'})
        d.addCallbacks(_cb,  _eb)

    def fetchTRTTrades(self, bootstrap=False):
        def _cb(res):
            try:
                res = json.loads(res)
                if res:
                    self.__fetchedTrades('trt.btceur', res, bootstrap=bootstrap)
                reactor.callLater(1, self.fetchTRTTrades)
            except Exception as e:
                self.unhandledError(e)
                reactor.callLater(5, self.fetchTRTTrades)
        def _eb(e):
            self.unhandledError(e)
            reactor.callLater(5, self.fetchTRTTrades)
        since = self.ticker['trt'][1] if self.ticker.has_key('trt') and len(self.ticker['trt']) > 0  \
            else int(time()-3600)
        d = getPage('https://www.therocktrading.com/api/trades/BTCEUR?since={}'.format(since),
                timeout=20,
                headers={'Accept': 'application/json'})
        d.addCallbacks(_cb,  _eb)

announcer = Announcer()
reactor.run()