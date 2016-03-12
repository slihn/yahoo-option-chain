"""
Grab option chain data from Yahoo Finance, especially implied volatility
"""

from urllib import request
from lxml import html
from time import gmtime, strftime
import logging
import sys
import time
from os import path


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
        logger.debug("Obtained expiry menu: %d - %s" % (expiry_ms, expiry_dt_iso))

    return menu


def get_option_chain(symbol: str, expiry_ms: int=None):
    tree = fetch_from_yahoo(symbol, expiry_ms)
    # <span id="yfs_l84_^XDE" data-sq="^XDE:value">109.00</span>
    value_elem = tree.find(".//span[@data-sq='%s:value']" % symbol)
    assert symbol in value_elem.get("id"), "Failed to locate price element"
    symbol2 = symbol.strip('^')
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
            if not row[1].startswith(symbol2):
                continue

            out += parse_tr_row(row, row_id, symbol2, price)

    return out


def parse_tr_row(row, row_id, symbol2, price):

    # row structure:
    # 0: Strike, 1: Contract Name,
    # 2: Last, 3: Bid, 4: Ask, 5: LAST, 6: L_BID, 7: L_ASK
    # 5: Change, 6: %Change, 7: Volume
    # 8: Open Interest, 9: Implied Volatility

    data = dict()
    ls = len(symbol2)
    contract = row[1]  # Contract Name
    put_call = contract[ls+6]
    assert symbol2 == contract[0:ls], "contract prefix is not symbol: %s vs %s" % (symbol2, contract)
    assert put_call == "P" or put_call == "C", "put_call is not P,C: %s" % put_call

    data['ROW'] = "%d" % row_id
    data['TRADE_DT'] = time.strftime("%Y%m%d")
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

    logger.info("Fetches data from %s" % url)
    res = request.urlopen(url)
    content = res.read()
    res.close()

    tree = html.fromstring(content)
    logger.debug("Html content is parsed")

    return tree


def save_symbol_data(symbol, file):
    out = ','.join(headings()) + "\n"

    logger.info("Fetches expiry menu")
    expiry_menu = None
    for attempt in range(3):
        try:
            expiry_menu = get_options_menu(symbol)
        except:
            logger.warn("Attempt %d failed to fetch expiry menu, wait..." % (attempt+1))
            time.sleep(10)
        else:
            break
    else:
        logger.error("Failed to fetch expiry menu")
        exit(1)

    expiry_list = list(expiry_menu.keys())
    expiry_list.sort()
    for expiry_ms in expiry_list:
        expiry_dt = gmtime(expiry_ms)
        expiry_dt_iso = strftime("%Y-%m-%d", expiry_dt)
        logger.info("Fetches chain data for %d - %s" % (expiry_ms, expiry_dt_iso))
        for attempt in range(3):
            try:
                chain_data = get_option_chain(symbol, expiry_ms)
                out += chain_data
            except:
                logger.warn("Attempt %d failed to fetch chain data, wait..." % (attempt+1))
                time.sleep(10)
            else:
                break
        else:
            logger.error("Failed to fetch chain data for %d - %s" % (expiry_ms, expiry_dt_iso))
            exit(1)

    file.write(out)
    file.flush()


def save_symbol_data_by_filename(symbol, filename):
    msg = "Output to %s" % filename
    logger.info(msg)
    print(msg)

    with open(filename, 'w') as f:
        save_symbol_data(symbol, f)
        f.close()
    logger.info("Data saved to %s" % filename)


def headings():
    return ['ROW', 'TRADE_DT', 'EXPR_DT', 'UNDL_PRC', 'PC', 'STRK_PRC',
            'OPT_SYMBOL', 'LAST', 'L_BID', 'L_ASK', 'CHANGE', 'PCT_CHANGE',
            'VOL', 'OIT', 'IVOL']


def usage():
    print("""grab-opt-chain.py: Grab option chain data from Yahoo Finance
usage:
    -h              Help
    -x dir          Save ^XDE data to a directory
    -x dir symbol   Save symbol data to a directory
    symbol          Grab data for a symbol, output to stdout
    symbol file     Grab data for a symbol, save output to file
    """)


# ------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == '-h':
        usage()
        exit(0)

    symbol_in = "^XDE"
    if len(sys.argv) >= 3 and sys.argv[1] == '-x':
        data_dir = sys.argv[2]
        if len(sys.argv) >= 4:
            symbol_in = sys.argv[3]
        dt_in = time.strftime("%Y%m%d")
        filename_in = path.join(data_dir, symbol_in.strip('^')+'-ivol-'+dt_in+".csv")
        save_symbol_data_by_filename(symbol_in, filename_in)
        exit(0)

    if len(sys.argv) >= 2:
        symbol_in = sys.argv[1]

    if len(sys.argv) >= 3:
        filename_in = sys.argv[2]
        save_symbol_data_by_filename(symbol_in, filename_in)
    else:
        save_symbol_data(symbol_in, sys.stdout)

# end of main
