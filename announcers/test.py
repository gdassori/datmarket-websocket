def fetch_txs():
    import requests, operator
    transactions = {}
    url = 'http://localhost:5980/sales/_design/maintenance/_view/id_and_timestamp'
    raw = requests.get(url).json()
    for i, v in enumerate(raw['rows']):
        transactions.update({raw['rows'][i]['id']:raw['rows'][i]['value'][0]})
    url = 'http://localhost:5980/sales/_design/maintenance/_view/submitted_orders'
    raw = requests.get(url).json()
    for i, v in enumerate(raw['rows']):
        transactions.update({raw['rows'][i]['id']:raw['rows'][i]['value'][0]})
    txs, timestamps = [], []
    sorted_transactions = sorted(transactions.iteritems(), key=operator.itemgetter(1))
    for i, v in enumerate(sorted_transactions):
        txs.append(sorted_transactions[i][0][::-1])
    return txs

def hash_to_fb(uuid, txs=None):
    if not txs: txs = fetch_txs()
    uuid = uuid[::-1]
    fb_len = None
    for n in range(4,10):
        fbs = [x[0:n] for x in txs]
        if fbs.count(uuid[0:n]) < 2:
            fb_len = n
            break
    if fb_len: return uuid[0:fb_len]
    else: return fb_len

def fb_to_hash(fb, txs=None):
    if not txs: txs = fetch_txs()
    fbs = [x[0:len(fb)] for x in txs]
    if fb not in fbs:
        return None
    else:
        return txs[fbs.index(fb)][::-1]

def test_fb():
    txs = fetch_txs()
    errors = 0
    print '{} Transactions'.format(len(txs))
    for tx in txs:
        if fb_to_hash(hash_to_fb(tx, txs=txs), txs=txs) != tx:
            errors += 1
    print '{} ERRORS'.format(errors)