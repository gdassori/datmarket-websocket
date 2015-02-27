var user = "client";
var key = "client_secret";  //todo: otp

function onchallenge (session, method, extra) {
    console.log("onchallenge", method, extra);
    if (method === "wampcra") {
        console.log("authenticating via '" + method + "' and challenge '" + extra.challenge + "'");
        return autobahn.auth_cra.sign(key, extra.challenge);
    } else {
        throw "don't know how to authenticate using '" + method + "'";
    }
}

var connection = new autobahn.Connection({
        url: 'ws://127.0.0.1:9000/ws',
        realm: 'datmarketPub',
        authmethods: ["wampcra"],
        authid: user,
        onchallenge: onchallenge}
);

connection.onopen = function (session, details) {
   console.log('connection opened');
    console.log("connected session with ID " + session.id);
    console.log("authenticated using method '" + details.authmethod + "' and provider '" + details.authprovider + "'");
    console.log("authenticated with authid '" + details.authid + "' and authrole '" + details.authrole + "'");

    function onAuthError(res) {
        console.log('authentication error');
        console.log(res)
    }
    function publishData(data) {
        var div = document.getElementById('events');
        div.innerHTML += data + "<br /><br />"
        div.scrollTop = div.scrollHeight;
    }

   function onEvent(event, args) {
      date = new Date();
      console.log(date + " | Got event: " + event + ": " + args[0]);
      publishData(date + " | Got event: " + event + ": " + args[0]);
   }

   function onCall(data) {
     date = new Date();
     publishData(date + " | Got call response: " + data)
     console.log(date + " | Got call response: " + data)
   }
    console.log('placing calls: tickers list and btce 1hour timeframe history...')
    //session.call('dm.tickers.list').then(function (res) { onCall(res) });
    for (i = 1; i < 3; i++) session.call('dm.history', ['bitstamp.btcusd.1h', i]).then(function (res) { onCall(res) });
    console.log('subscribing to bitstamp.btcusd tickers and 1hours new candles...');
    session.subscribe('dm.ohlc.bitstamp.btcusd.1h', function (res) { onEvent('dm.ohlc.bitstamp.btcusd.1h', res) })
    session.subscribe('dm.tickers.bitstamp.btcusd', function (res) { onEvent('dm.tickers.bitstamp.btcusd', res) })
};

function setSize() {
    var w = window,
        d = document,
        e = d.documentElement,
        g = d.getElementsByTagName('body')[0],
        x = w.innerWidth || e.clientWidth || g.clientWidth,
        y = w.innerHeight|| e.clientHeight|| g.clientHeight;
    document.body.style.width = x * 0.9 + "px"
    document.body.style.height = y * 0.9 + "px"
    var div = document.getElementById('events');
    div.style.width = x * 0.8 + "px"
    div.style.height = y * 0.8 + "px"
    div.style.marginLeft = x * 0.1 + "px"
    }

if(window.attachEvent) {
    window.attachEvent('onresize', function() {
        setSize()
    });
}
else if(window.addEventListener) {
    window.addEventListener('resize', function() {
        setSize()
    }, true);
}
else {
    //The browser does not support Javascript event binding
}
connection.open();

