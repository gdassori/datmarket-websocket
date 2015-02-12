from autobahn.twisted.wamp import ApplicationSession
from autobahn.twisted.wamp import ApplicationSessionFactory, WampWebSocketClientFactory
from twisted.internet.endpoints import clientFromString
from autobahn.wamp import types
from twisted.internet import reactor
from autobahn.wamp import auth
import json
from time import time

class App(ApplicationSession):
    def unhandledError(self, reason, data):
        print "UNHANDLED ERROR: {} | {}".format(reason, data)

    def onJoin(self, data):
        print "Frontend joined on {}".format(self.config.realm)
        self.lastTickerBroadcasted = {}
        self.BROADCAST_TICKER_INTERVAL = 1
        self.channels = ["trt.btceur",
                         "btce.btcusd", "btce.btceur",
                         "bitstamp.btcusd"]

        self.cb = Cb()
        self.serverApp = ServerApp(self)
        self.register(self.returnChannels, 'dm.tickers.list')
        self.connectToWampServer()

    def newTicker(self, channel, data):
        if not self.lastTickerBroadcasted.has_key(channel) or \
            int(time()) - self.lastTickerBroadcasted[channel] >= self.BROADCAST_TICKER_INTERVAL:
            self.publish('dm.tickers.{}'.format(channel), json.dumps(data))
            print 'new ticker received and republished, {}: {}'.format(channel, data)

    def returnChannels(self):
        return json.dumps(self.channels)

    def connectToWampServer(self):
        self.serverConnection = clientFromString(reactor, "tcp:127.0.0.1:8080")
        self.serverConnection.connect(self.serverApp.server_transport_factory)

class ServerApp():
    def __init__(self, frontend):
        self.channels = frontend.channels
        self.series = {}
        self.frontend = frontend
        self.cb = Cb()
        self.on = {'connect': self.onConnect, 'disconnect': self.onDisconnect, 'joined': self.onJoin}
        self.server_component_config = types.ComponentConfig(realm = u"datmarket0")
        self.authData = {'user': u'frontend', 'secret': u'frontend_secret'}
        self.server_factory = ApplicationSessionFactory(config = self.server_component_config)
        self.server_factory.session = lambda :wampClient(self.cb,
                                                         self.server_component_config,
                                                         self.on,
                                                         self.authData)
        self.server_transport_factory = WampWebSocketClientFactory(self.server_factory.session,
                                                                   url="ws://localhost:8080/ws",
                                                                   debug = False,
                                                                   debug_wamp = False)
    def onConnect(self):
        pass

    def onDisconnect(self, wasClean):
        pass

    def onJoin(self):
        self.subscribeChannels()

    def subscribeChannels(self):
        for channel in self.channels:
            print "subscribed to {}".format(channel)
            self.cb.wamp.subscribe(lambda data, channel=channel: self.frontend.newTicker(channel, data), "dm.tickers.{}".format(channel))

class Cb():
    def __init__(self):
        self.wamp = None
    def _set_wamp(self, wamp):
        self.wamp = wamp

class wampClient(ApplicationSession):
    def __init__(self, callback, config, onEvent, authData):
        self.authData = authData
        print 'wamp server initialized'
        ApplicationSession.__init__(self, config=config)
        self.callback = callback
        callback._set_wamp(self)
        self.channels = []
        self.onEvent = onEvent

    def onConnect(self):
        self.join(self.config.realm, [u"wampcra"], self.authData['user'])
        self.onEvent['connect']()

    def onClose(self, wasClean):
        self.onEvent['disconnect'](wasClean)

    def onChallenge(self, challenge):
        if challenge.method == u"wampcra":
            signature = auth.compute_wcs(self.authData['secret'].encode('utf8'), challenge.extra['challenge'].encode('utf8'))
            return signature.decode('ascii')
        else:
            raise Exception("don't know how to handle authmethod {}".format(challenge.method))

    def onJoin(self, details):
        print "Frontend joined {}, session ready".format(self.config.realm)
        self.onEvent['joined']()