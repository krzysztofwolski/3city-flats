#!/usr/bin/python

from urllib.request import urlopen
from bs4 import BeautifulSoup
import logging as log
import smtplib
import sys
import time
import argparse
from email.mime.text import MIMEText

FORMAT="%(asctime)-15s %(message)s"
URL="http://ogloszenia.trojmiasto.pl/nieruchomosci-mam-do-wynajecia/wi,100,ai,_1800,e1i,38_35_3_34_36_87_5_2,ri,_2,na,1,has_hv,1,o0,0.html"
MAILSRV="smtp.gmail.com:587"
FROM="janfmusial@gmail.com"
TO="janfmusial+flats@gmail.com"
USER="janfmusial@gmail.com"
TIMEOUT=60
VERBOSITY=20
CACHE="offers.dat"

class Flat:
    def __init__(self, link, price="", size="", location="", title=""):
        self.link = link
        self.price = "" if price is None else price
        self.size = "" if size is None else size
        self.location = "" if location is None else location
        self.title = "" if title is None else title

    def __eq__(self, other):
        return self.link == other.link

    def __str__(self):
        return self.link

class Cache:
    def __init__(self, purge=False):
        self.cache = []

        if not purge:
            self.cache = self.readOffers(CACHE)
        
        self.f = open(CACHE, "w")

    def readOffers(self, path):
        try:
            f = open(path, "r")
        except:
            return []

        cache = []
        for entry in f:
            cache.append(Flat(entry.rstrip()))
        
        f.close()
        return cache

    def offerExists(self, offer):
        return offer in self.cache

    def addOffer(self, offer):
        if offer in self.cache:
            return

        self.cache.append(offer)

    def flushCache(self):
        for offer in self.cache:
            self.f.write(str(offer) + "\n")

    def closeCache(self):
        self.f.close()

    def __del__(self):
        self.closeCache()

def emailLogin(server, user, password):
    srv = smtplib.SMTP(server)
    srv.ehlo()
    srv.starttls()
    srv.login(user, password)
    return srv

def parseLinks(url):
    response = urlopen(url)
    html = response.read()

    soup = BeautifulSoup(html, "html.parser")
    
    offers = []

    # find all offer headers
    for offer in soup.find_all("li", class_="list-elem"):
        header = offer.find("div", class_="ogl-head")
        title = header.h2.a.get_text()
        link  = header.h2.a.get("href")

        body = offer.find("div", class_="ogl-content")
        price = body.find("li", class_="price").get_text()
        location = body.find("li", class_="place").get_text()
        price = body.find("li", class_="price").get_text()
        size = body.find("li", class_="size").get_text()
        offers.append(Flat(link=link, price=price, size=size, location=location, title=title))

    return offers

def sendNotification(server, flat):
    msg = MIMEText(flat.link)
    msg['From'] = FROM
    msg['To'] = TO
    msg['Subject'] = "{} {} | {} {}".format(flat.location, flat.price, flat.size, flat.title)
    server.send_message(msg)

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbosity", default=20, help="logging verbosity", type=int)
    parser.add_argument("-d", "--purge", action="store_true", help="purge cache") 
    parser.add_argument("-f", "--sender", default=FROM, help="sender address", type=str)
    parser.add_argument("-t", "--to", default=TO, help="to address", type=str)
    parser.add_argument("-x", "--timeout", default=TIMEOUT, help="polling interval", type=int)
    parser.add_argument("-s", "--mailserver", default=MAILSRV, help="mail server address:port", type=str)
    parser.add_argument("-u", "--user", help="mail server user", required=True, type=str)
    parser.add_argument("-p", "--password", help="mail server password", required=True, type=str)
    args = parser.parse_args()

    VERBOSITY = args.verbosity
    PURGE = args.purge
    FROM = args.sender
    TO = args.to
    MAILSRV = args.mailserver
    USER = args.user
    PWD = args.password
    TIMEOUT=args.timeout

    offer_cache = Cache(PURGE)

    log.basicConfig(format=FORMAT)
    l = log.getLogger("default")
    l.setLevel(VERBOSITY)
    
    l.info("Starting FlatFinder")
    l.debug("Attempting GMail login")
    try:
        mailsrv = emailLogin(MAILSRV, USER, PWD)
    except:
        l.critical("GMail login failed. Exception occured: %s", sys.exc_info()[1])
        sys.exit(1)
    l.info("GMail login successful")

    try:
        while True:
            l.debug("Fetching offers")
            flats = parseLinks(URL)
            l.debug("Fetched %d offers", len(flats))

            for flat in flats:
                if not offer_cache.offerExists(flat):
                    l.info("New offer discovered at %s", flat.link)
                    l.debug("Title: %s | Location: %s | Price: %s | Size: %s", flat.title, flat.location, flat.price, flat.size)
                    sendNotification(mailsrv, flat)
                    offer_cache.addOffer(flat)
                
            time.sleep(TIMEOUT)

    except KeyboardInterrupt:
        mailsrv.quit()
        offer_cache.flushCache()
        l.info("Quitting...")
        sys.exit(0)


