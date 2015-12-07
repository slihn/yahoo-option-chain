"Grab option chain data from Yahoo Finance, especially implied volatility"

from urllib import request
from lxml import html
# from lxml import etree
from time import gmtime, strftime
import logging
import sys


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
    for exp in options_menu.findall(".//option"):
        exp_ms = int(float(exp.get("value")))
        exp_dt = gmtime(exp_ms)
        exp_dt_iso = strftime("%Y-%m-%d", exp_dt)
        exp_tm_iso = strftime("%H:%M:%S", exp_dt)
        assert exp_tm_iso == "00:00:00", "Expiration assertion failed: %d %s %s" % (exp_ms, exp_dt_iso, exp_tm_iso)
        menu[exp_ms] = exp_dt_iso
        logger.debug("Expiry %d: %s" % (exp_ms, exp_dt_iso))

    return menu


def get_option_chain(symbol: str, dt: int=None):
    tree = fetch_from_yahoo(symbol, dt)
    # <span id="yfs_l84_^XDE" data-sq="^XDE:value">109.00</span>
    value_elem = tree.find(".//span[@data-sq='%s:value']" % symbol)
    assert symbol in value_elem.get("id"), "Failed to locate price element"
    price = value_elem.text # UNDL_PRC

    # <div id="quote-table">
    quote_table = tree.find(".//div[@id='quote-table']")
    # <table class="details-table quote-table Fz-m">
    for data_table in quote_table.findall(".//table"):
        # etree.dump(data_table)
        for tr in data_table.findall(".//tr"):
            row_id = tr.get("data-row")
            if row_id is not None:
                row_id = int(row_id)
                row = [td.xpath("normalize-space()") for td in tr.findall("./td")]
                if not row[1].startswith(symbol.strip('^')):
                    continue
                contract = row[1]
                put_call = contract[len(symbol)+6-1]
                assert put_call=="P" or put_call== "C", "put_call is not P,C"
                row[6] = "%4.2f" % p2f(row[6])
                row[9] = "%4.2f" % p2f(row[9])
                print("%2d,%s,%s," % (row_id, price, put_call), ",".join(row))

                # TRADE_DT
                # 0: Strike STRK_PRC, Contract Name,
                # 2: Last, Bid, Ask, LAST,    L_BID,    L_ASK
                # 5: Change, %Change, Volume, VOL
                # 8: Open Interest, Implied Volatility

                # CBOE Style
                # TRADE_DT, UNDLY, CLS,  EXPR_DT, STRK_PRC, PC,    OIT,   VOL,  HIGH,   LOW,  OPEN,  LAST,    L_BID,    L_ASK, UNDL_PRC,  S_TYPE,P_TYPE
                # 20150601,   SPX, SPX, 20150619, 100.0000,  C, 2.0000,0.0000,0.0000,0.0000,0.0000,0.0000,2006.8000,2011.1000,2111.7300,Standard,Index

    return


def p2f(x):
    return float(x.strip('%'))/100


def fetch_from_yahoo(symbol, dt):
    url = "http://finance.yahoo.com/q/op?s=%s+Options" % symbol
    if dt is not None:
        url = url + "&date=" + str(dt)

    logger.info("Fetch data from %s" % url)
    res = request.urlopen(url)
    content = res.read()
    res.close()

    tree = html.fromstring(content)
    logger.debug("Html content is parsed")

    return tree


symbol = "^XDE"
get_options_menu(symbol)
get_option_chain(symbol)