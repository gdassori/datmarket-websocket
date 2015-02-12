from influxdb import InfluxDBClient
from autobahn.twisted.wamp import ApplicationSession
from time import time

class App(ApplicationSession):

    def unhandledError(self, reason, data):
        print "UNHANDLED ERROR: {} | {}".format(reason, data)

    def onJoin(self, data):
        print "DBMS joined on {}".format(self.config.realm)
        self.dbcli = InfluxDBClient('localhost', 8086, 'root', 'root', '')
        self.lastTickerSaved = {}
        self.SAVE_TICKER_INTERVAL = 1
        self.subscriptions = ["trt.btceur",
                              "btce.btcusd", "btce.btceur",
                              "bitstamp.btcusd"]
        self.createDatabase()
        self.subscribeEvents()

    def createDatabase(self):
        for channel in self.subscriptions:
            try: self.dbcli.create_database("{}.tickers".format(channel))
            except: pass

    def subscribeEvents(self):
        for sub in self.subscriptions:
            print "subscribing dm.tickers.{}.{}".format
            self.subscribe(lambda data, sub=sub: self.processTicker(data, sub), "dm.tickers.{}".format(sub))

    def processTicker(self, data, subscription):
        print 'received {}: {}'.format(subscription, data)
        try:
            float(data)
        except:
            print 'received non float for {}, refusing {}'.format(subscription, data)
            return False
        now = int(time())
        if not self.lastTickerSaved.has_key(subscription) or now - self.lastTickerSaved[subscription] >= self.SAVE_TICKER_INTERVAL:
            self.lastTickerSaved[subscription] = now
            provider, pair = subscription.split(".")
            print "{} relevant, saving".format(subscription)
            self.writeTicker(provider, pair, data)

    def writeTicker(self, provider, pair, data):
        self.dbcli.switch_database("{}.{}.tickers".format(provider, pair))
        points = [pair, data]
        data = [{"name": "ticker",
                 "columns": ["pair", "price"],
                 "points": [points]}]
        try:
            self.dbcli.write_points(data, time_precision='s')
        except:
            print 'ERROR WRITING ' + str(data)