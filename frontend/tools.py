def migrateDatabase():
    # non production, used only for database migration during development
    from influxdb import InfluxDBClient
    cli = InfluxDBClient('localhost', 8086, 'root', 'root', '')
    cli.switch_database('trt')
    query = "SELECT price from trt where pair = 'BTCEUR'"
    res = cli.query(query)
    cli.switch_database('trt.btceur.tickers')
    for x in res[0]['points']:
        points = [x[0], 'btceur', x[2]]
        data = [{"name": "ticker",
                 "columns": ["time", "pair", "price"],
                 "points": [points]}]
        cli.write_points(data, time_precision='s')
    print 'done'
