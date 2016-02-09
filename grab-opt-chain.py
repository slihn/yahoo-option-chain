"""
Grab option chain data from Yahoo Finance, especially implied volatility
"""

from urllib import request
from lxml import html
from time import gmtime, strftime
import logging
import sys
import time


logger = logging.getLogger(__name__)

logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


def get_options_menu(symbol: str, dt: int=None):
    tree = fetch_from_yahoo(symbol, dt)
    # <div id="quote-table">
    quote_table = tree.find(".//div[@id='quote-table']")
    #   <div id="options_menu" class="Grid-U options_menu">
    options_menu = quote_table.find(".//div[@id='options_menu']/form")
    # etree.dump(options_menu)

    menu = dict()
    for expiry in options_menu.findall(".//option"):
        expiry_ms = int(float(expiry.get("value")))  # epoch time
        expiry_dt = gmtime(expiry_ms)
        expiry_dt_iso = strftime("%Y-%m-%d", expiry_dt)
        expiry_tm_iso = strftime("%H:%M:%S", expiry_dt)
        assert expiry_tm_iso == "00:00:00", \
            "Expiration assertion failed: %d %s %s" % (expiry_ms, expiry_dt_iso, expiry_tm_iso)
        menu[expiry_ms] = expiry_dt_iso
        logger.debug("Expiry %d: %s" % (expiry_ms, expiry_dt_iso))

    return menu


def get_option_chain(symbol: str, expiry_ms: int=None):
    tree = fetch_from_yahoo(symbol, expiry_ms)
    # <span id="yfs_l84_^XDE" data-sq="^XDE:value">109.00</span>
    value_elem = tree.find(".//span[@data-sq='%s:value']" % symbol)
    assert symbol in value_elem.get("id"), "Failed to locate price element"
    price = value_elem.text  # UNDL_PRC

    # <div id="quote-table">
    quote_table = tree.find(".//div[@id='quote-table']")
    # <table class="details-table quote-table Fz-m">

    out = ""
    for data_table in quote_table.findall(".//table"):
        # etree.dump(data_table)
        for tr in data_table.findall(".//tr"):
            row_id = tr.get("data-row")
            if row_id is None:
                continue

            row_id = int(row_id)
            row = [td.xpath("normalize-space()") for td in tr.findall("./td")]
            if not row[1].startswith(symbol.strip('^')):
                continue

            out += parse_tr_row(row, row_id, symbol, price)

    return out


def parse_tr_row(row, row_id, symbol, price):

    # row structure:
    # 0: Strike, 1: Contract Name,
    # 2: Last, 3: Bid, 4: Ask, 5: LAST, 6: L_BID, 7: L_ASK
    # 5: Change, 6: %Change, 7: Volume
    # 8: Open Interest, 9: Implied Volatility

    data = dict()
    data['ROW'] = "%2d" % row_id
    data['TRADE_DT'] = time.strftime("%Y%m%d")

    ls = len(symbol)
    symbol2 = symbol
    if symbol[0] == '^':
        ls -= 1
        symbol2 = symbol[1:1+ls]

    contract = row[1]  # Contract Name
    put_call = contract[ls+6]
    assert symbol2 == contract[0:ls], "contract prefix is not symbol: %s vs %s" % (symbol2, contract)
    assert put_call == "P" or put_call == "C", "put_call is not P,C: %s" % put_call

    data['EXPR_DT'] = "20%s" % contract[ls:ls+6]
    data['UNDL_PRC'] = price
    data['PC'] = put_call
    data['STRK_PRC'] = row[0]
    data['OPT_SYMBOL'] = contract
    data['LAST'] = row[2]
    data['L_BID'] = row[3]
    data['L_ASK'] = row[4]
    data['CHANGE'] = row[5]
    data['PCT_CHANGE'] = "%4.2f" % p2f(row[6])
    data['VOL'] = row[7]
    data['OIT'] = row[8]
    data['IVOL'] = "%4.2f" % p2f(row[9])

    out = ','.join([data[k] for k in headings()]) + "\n"
    return out


def p2f(x):
    return float(x.strip('%'))/100


def fetch_from_yahoo(symbol, expiry_ms):
    url = "http://finance.yahoo.com/q/op?s=%s+Options" % symbol
    if expiry_ms is not None:
        url = url + "&date=" + str(expiry_ms)

    logger.info("Fetch data from %s" % url)
    res = request.urlopen(url)
    content = res.read()
    res.close()

    tree = html.fromstring(content)
    logger.debug("Html content is parsed")

    return tree


def get_xde_data():
    out = ','.join(headings()) + "\n"
    symbol = "^XDE"
    expiry_menu = get_options_menu(symbol)
    for expiry_ms in expiry_menu.keys():
        out += get_option_chain(symbol, expiry_ms)
    return out


def headings():
    return ['ROW', 'TRADE_DT', 'EXPR_DT', 'UNDL_PRC', 'PC', 'STRK_PRC',
            'OPT_SYMBOL', 'LAST', 'L_BID', 'L_ASK', 'CHANGE', 'PCT_CHANGE', 'VOL', 'OIT', 'IVOL']


# ------------------------------------------
if __name__ == "__main__":
    print(get_xde_data())

# end of main
