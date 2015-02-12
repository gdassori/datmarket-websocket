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
        self.REFETCH_AFTER = 1
        self.IF_FETCH_FAIL_RETRY_AFTER = 3
        self.channels = {'btce': ['btcusd', 'btceur'], 'trt': ['btceur'], 'bitstamp': ['btcusd']}
        self.cb = Cb()
        self.onEvents = {"join": self.onJoin, "close": self.onClose}
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
                                                                   debug = False,
                                                                   debug_wamp = False)
        tryToConnect()

    def unhandledError(self, data):
        print 'unhandled error: {}'.format(data)

    def onJoin(self):
        self.isOnline = True
        self.publishBitstamp(self.publishEvent, self.unhandledError)
        self.publishBTCe(self.publishEvent, self.unhandledError)
        self.publishTRT(self.publishEvent, self.unhandledError)
        self.resetTicker()

    def resetTicker(self):
        """
        be sure to rebroadcast all tickers @ 0 second of every minute, also if time is less than
        """
        now = int(time())
        if now % 60 == 0:
            self.latestPublishedTickers = {}
            reactor.callLater(2, self.resetTicker)
        else:
            reactor.callLater(0.5, self.resetTicker)

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

    def publishEvent(self, provider, data):
        if provider in self.channels.viewkeys():
            for key in data.viewkeys():
                if key in self.channels[provider]:
                    if not self.latestPublishedTickers.has_key(provider+"."+key) or \
                                    data[key] != self.latestPublishedTickers[provider+"."+key]:
                        try:
                            self.cb.cli.publish("dm.tickers.{}.{}".format(provider, key), data[key])
                            self.latestPublishedTickers[provider+"."+key] = data[key]
                            print "{} | published dm.tickers.{}.{}: {}".format(strftime("%c"), provider, key, data[key])
                        except TransportLost:
                            pass
                else:
                    print 'error, invalid ticker for provider, I will not broadcast: {} {}'.format(provider, key)
        else:
            print 'error, invalid provider, I will not broadcast: {}'.format(provider)

    def publishTRT(self, cb, eb):
        def _cb(data):
            try:
                data = json.loads(data)
            except:
                _eb({'error': 'nojson'})
            res = {'btceur': float(data['result']['tickers']['BTCEUR']['last'])}
            if self.isOnline: reactor.callLater(self.REFETCH_AFTER, lambda: self.publishTRT(cb, eb))
            cb('trt', res)
        def _eb(data):
            eb(data)
            print "error calling trt ticker, retry in 3 seconds"
            if self.isOnline: reactor.callLater(self.IF_FETCH_FAIL_RETRY_AFTER, lambda: self.publishTRT(cb, eb))
        d = getPage('https://www.therocktrading.com/api/tickers/',
                    timeout=20,
                    headers={'Accept': 'application/json'})
        d.addCallbacks(_cb, _eb)

    def publishBitstamp(self, cb, eb):
        def _cb(data):
            try:
                data = json.loads(data)
            except:
                print 'exception, no valid json'
                _eb({'error': 'nojson'})
            res = {'btcusd': float(data['last'])}
            if self.isOnline: reactor.callLater(self.REFETCH_AFTER, lambda: self.publishBitstamp(cb, eb))
            cb('bitstamp', res)
        def _eb(data):
            eb(data)
            print "error calling Bitstamp ticker, retry in 3 seconds"
            if self.isOnline: reactor.callLater(self.IF_FETCH_FAIL_RETRY_AFTER, lambda: self.publishBitstamp(cb, eb))
        d = getPage('https://www.bitstamp.net/api/ticker/',
                timeout=20,
                headers={'Accept': 'application/json'})
        d.addCallbacks(_cb, _eb)

    def publishBTCe(self,cb, eb):
        def _cb(data):
            try:
                data = json.loads(data)
            except:
                _eb({'error': 'nojson'})
            res = {'btcusd': float(data['btc_usd']['last']),
                   'btceur': float(data['btc_eur']['last'])}
            if self.isOnline: reactor.callLater(self.REFETCH_AFTER, lambda: self.publishBTCe(cb, eb))
            cb('btce', res)
        def _eb(data):
            eb(data)
            print "error calling BTCe ticker, retry in 3 seconds"
            if self.isOnline: reactor.callLater(self.IF_FETCH_FAIL_RETRY_AFTER, lambda: self.publishBTCe(cb, eb))
        d = getPage('https://btc-e.com/api/3/ticker/btc_usd-btc_eur',
                timeout=20,
                headers={'Accept': 'application/json'})
        d.addCallbacks(_cb, _eb)

announcer = Announcer()
reactor.run()