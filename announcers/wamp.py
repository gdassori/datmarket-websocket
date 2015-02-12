from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp import auth

class wampClient(ApplicationSession):
    def __init__(self, callback, config, on):
        ApplicationSession.__init__(self, config=config)
        self.callback = callback
        callback._set_cli(self)
        self.authData = {'user': u'announcer1', 'secret': u'announcer1_secret'}
        self.onEvent = on

    def onConnect(self):
        self.join(self.config.realm, [u"wampcra"], self.authData['user'])

    def onChallenge(self, challenge):
        if challenge.method == u"wampcra":
            signature = auth.compute_wcs(self.authData['secret'].encode('utf8'), challenge.extra['challenge'].encode('utf8'))
            return signature.decode('ascii')
        else:
            raise Exception("don't know how to handle authmethod {}".format(challenge.method))

    def onJoin(self, details):
        print "joined {}, session ready".format(self.config.realm)
        self.onEvent['join']()

    def onClose(self, wasClean):
        self.onEvent['close'](wasClean)
