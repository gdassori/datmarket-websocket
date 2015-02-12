from influxdb import InfluxDBClient
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp import auth
import json
from time import time
from twisted.internet import reactor

class App(ApplicationSession):
    # TODO handle trades and bring OHLC to OHLCV
    def unhandledError(self, reason, data):
        print "UNHANDLED ERROR: {} | {}".format(reason, data)

    def onConnect(self):
        self.authData = {'user': u'broadcaster', 'secret': u'broadcaster_secret'}
        self.join(self.config.realm, [u"wampcra"], self.authData['user'])

    def onChallenge(self, challenge):
        if challenge.method == u"wampcra":
            signature = auth.compute_wcs(self.authData['secret'].encode('utf8'), challenge.extra['challenge'].encode('utf8'))
            return signature.decode('ascii')
        else:
            raise Exception("don't know how to handle authmethod {}".format(challenge.method))

    def onJoin(self, data):
        print "OHLC manager joined on {}".format(self.config.realm)
        self.dbcli = InfluxDBClient('localhost', 8086, 'root', 'root', '')
        self.SAVE_TICKER_INTERVAL = 1
        self.JSON_BACKUP_INTERVAL = 1800 # seconds
        self.json_backup_timestamp = {}
        self.subscriptions = ["trt.btceur",
                              "btce.btcusd", "btce.btceur",
                              "bitstamp.btcusd"]
        self.candlesManager = candlesManager(self.dbcli)
        self.candles = {}
        self.loadOHLC()
        self.registerChannels()

    def registerChannels(self):
        print "registering Channel"
        self.register(self.pushChannel, 'dm.history')

    def pushChannel(self, channel, page=1):
        if channel.lstrip('dm.history.') in self.candles.viewkeys():
            endsTo = page * 50 if page > 1 else 50
            resp = self.candles[channel][endsTo-50:endsTo]
            if resp:
                return json.dumps(resp)
            else:
                return json.dumps({"error": "out of range"})
        else:
            print "REQUESTED UNAVAILABLE CHANNEL: {}".format(channel) # warning
            return json.dumps({"error": "channel unavailable"})

    def loadOHLC(self):
        print "initializing OHLC"
        def cb(data):
            print "initializing OHLC on {}".format(channel)
            self.candles[channel] = data
            self.__buildMissingOHLC(channel)
        def eb(e, channel):
            def _cb(data):
                self.candles[channel] = data
                self.__buildMissingOHLC(channel, fileExist=False)
            print e
            print "OHLC file not loaded, rebuilding (loadOHLC): {}".format(channel)
            failureReason = "FAILURE - unable to load OHLC data, nor to rebuild it"
            self.candlesManager.buildOHLC(channel, _cb, lambda res: self.unhandledError(failureReason, res))

        for subscription in self.subscriptions:
            provider, pair = subscription.split(".")
            for timeframe in self.candlesManager.config['ranges'].viewkeys():
                channel = provider+"."+pair+"."+timeframe
                self.candlesManager.loadOHLC(channel, cb, eb)
                self.checkNewCandles(channel) # start cycle on each candle, this is going to be heavy when pair increases

    def __buildMissingOHLC(self, channel, fileExist=True, save_file=True, publish=False, checkLoop=False):
        def cb(data):
            howMany = len(self.candles[channel])
            data.reverse()
            if data:
                for candle in data:
                    if not candle[0] in available_candles:
                        self.candles[channel].insert(0, candle)
                        if publish: self.publishNewCandle(channel, candle)
            if checkLoop:
                reactor.callLater(1, lambda channel=channel: self.checkNewCandles(channel))
            diff = len(self.candles[channel]) - howMany
            if diff >= 1:
                print "(missing) candles built for {}: {}".format(channel, diff)
            if save_file and fileExist and howMany != len(self.candles[channel]):
                print "saving {} missing candle(s) on previous existing {} json file".format(diff, channel)
                self.__saveOHLC(channel)
            elif save_file and not fileExist:
                print "saving {} candles for {} (no json file previous exists)".format(len(self.candles[channel]),
                                                                                       channel)
                self.__saveOHLC(channel)
        def eb(res):
            print "ERROR with OHLC (buildMissing): {}".format(res)
        available_candles = [x[0] for x in self.candles[channel]]
        self.candlesManager.buildOHLC(channel, cb, eb, startsFrom=available_candles[0])

    def __saveOHLC(self, channel):
        def cb(channel):
            print 'OHLC JSON backup successful saved for {}'.format(channel)
            self.json_backup_timestamp[channel] = int(time())
        def eb(res, e):
            self.unhandledError("Unable to save OHLC for {}".format(res), e)
        candles = self.candles[channel]
        self.candlesManager.writeOHLC(channel, candles, cb, eb)

    def checkNewCandles(self, channel):
        now = int(time())
        lastCandle = self.candles[channel][0][0]
        timeframe = channel.split(".")[2]
        min_interval = self.candlesManager.config['ranges'][timeframe][2]
        if now % 60 == 59:
            if self.candles.has_key(channel) and len(self.candles[channel]) >= 1:
                if now - lastCandle >= min_interval:
                    saveFile = not self.json_backup_timestamp.has_key(channel) or \
                               now - self.json_backup_timestamp[channel] >  self.JSON_BACKUP_INTERVAL
                    self.__buildMissingOHLC(channel, save_file=saveFile, publish=True, checkLoop=True)
                else:
                    reactor.callLater(0.1, lambda channel=channel: self.checkNewCandles(channel))
            else:
                reactor.callLater(15, lambda channel=channel: self.checkNewCandles(channel))

    def publishNewCandle(self, channel, candle):
        if candle: self.publish("dm.ohlc.{}".format(channel), json.dumps(candle))
        print "new candle published on {}".format(channel)
        self.checkNewCandles(channel)


class candlesManager():
    #todo Volume from trades history
    def __init__(self, dbcli):
        self.cli = dbcli
        self.JSON_BACKUP_PATH = "json_files/"
        self.config = {'ranges': {'1h':  ['1h', '1m', 60],
                                  '3h':  ['3h', '5m', 300],
                                  '12h': ['12h', '15m', 900],
                                  '1d':  ['1d','30m', 1800],
                                  '1w':  ['7d', '4h', 14400],
                                  '30d': ['30d', '12h', 43202],
                                  '6m':  ['180d', '2d', 172802],
                                  '1y':  ['365d', '1w', 604802],
                                  '2y':  ['730d', '2w', 1209602]}
        } # [timeframe, candle size (influx group by), candle size in s]

    def buildOHLC(self, channel, cb, eb, startsFrom=0, endsTo=0):
        try:
            provider, pair, timeframe = channel.split(".")
            ranges = self.config['ranges']
            self.cli.switch_database("{}.{}.tickers".format(provider, pair))
            if not startsFrom and not endsTo:
                queryStr = "SELECT FIRST(price), MAX(price), MIN(price), LAST(price) from ticker group by time({}) where time > now() - {}"
                formattedQS = queryStr.format(ranges[timeframe][1], ranges[timeframe][0])
            elif startsFrom and not endsTo:
                queryStr = "SELECT FIRST(price), MAX(price), MIN(price), LAST(price) from ticker group by time({}) where time > {}s"
                formattedQS = queryStr.format(ranges[timeframe][1], startsFrom)
            elif startsFrom and endsTo:
                queryStr = "SELECT FIRST(price), MAX(price), MIN(price), LAST(price) where time > {}s and time < {}s"
                formattedQS = queryStr.format(ranges[timeframe][1], startsFrom, endsTo)
            else:
                eb({'status': 'error', 'msg': 'wrong params'})
                return False
            res = self.cli.query(formattedQS)[0]['points']
            if res: cb(res)
            else: eb(res)
        except Exception as e:
            eb(e)

    def writeOHLC(self, channel, candles, cb, eb):
        try:
            filename = "{}ohlc_{}.json".format(self.JSON_BACKUP_PATH, channel)
            print "writing a total of " + str(len(candles)) + " candles for {}".format(channel)
            with open(filename, 'w') as outfile:
                json.dump(candles, outfile)
            cb(channel)
        except Exception as e:
            eb(channel, e)

    def loadOHLC(self, channel, cb, eb):
        try:
            filename = "{}ohlc_{}.json".format(self.JSON_BACKUP_PATH, channel)
            with open(filename, 'r') as outfile:
                res = json.load(outfile)
            if res: cb(res)
            else: eb(channel)
        except Exception as e:
            eb(e, channel)

if __name__ == '__main__':
   runner = ApplicationRunner(url = u"ws://localhost:9000/ws", realm = u"datmarketPub", debug= True, debug_wamp= True)
   runner.run(App)