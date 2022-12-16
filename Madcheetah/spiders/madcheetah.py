from datetime import datetime
import json
import re

import scrapy
from scrapy import Request


class MadcheetahSpider(scrapy.Spider):
    name = 'madcheetah'
    start_urls = ['https://bid.madcheetah.com/auctions']
    url = "https://bid.madcheetah.com/auctions"

    zyte_key = ''  # Todo : YOUR API KEY FROM ZYTE
    custom_settings = {
        'FEED_URI': 'bid.csv',
        'FEED_FORMAT': 'csv',
        'ZYTE_SMARTPROXY_ENABLED': False,
        'ZYTE_SMARTPROXY_APIKEY': zyte_key,
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy_zyte_smartproxy.ZyteSmartProxyMiddleware': 610
        },
    }

    payload = {
        "_csrf": "",
        "timezone": "Europe/Stockholm",
        "auction": {
            "status": "upcoming",
            "location": "all",
            "type": "all"
        },
        "lot": {
            "location": "all",
            "category": "all",
            "mile_radius": 25
        },
        "page": 1,
        "limit": 10000
    }

    lot_url = "https://bid.madcheetah.com/lots"

    lot_payload = {
        "_csrf": "",
        "timezone": "Europe/Stockholm",
        "grab_featured_lots": True,
        "auction": {
            "id": "8023",
            "location": "all",
            "status": "upcoming",
            "type": "all"
        },
        "limit": "10000",
        "lot": {
            "category": "all",
            "location": "all",
            "mile_radius": "25",
            "state": "all"
        },
        "page": "1",
        "prev": {
            "wid": 74,
            "page": "l"
        }
    }
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://bid.madcheetah.com',
        'Referer': 'https://bid.madcheetah.com/auctions',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/107.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"'
    }

    def parse(self, response, **kwargs):
        token = ''.join(re.findall("Csrf = '(.+)'", response.text))
        self.payload['_csrf'] = token
        yield Request(
            url=self.url,
            headers=self.headers,
            body=json.dumps(self.payload),
            method='POST',
            callback=self.auctions,
            meta={'token': token}
        )

    def auctions(self, response):
        json_data = json.loads(response.text).get('data', {}).get('auctions', {})
        for auction in json_data:
            self.lot_payload['auction']['id'] = auction.get('id', '')
            self.lot_payload['_csrf'] = response.meta['token']
            yield Request(
                url=self.lot_url,
                headers=self.headers,
                body=json.dumps(self.lot_payload),
                method='POST',
                callback=self.lot,
                meta={'token': response.meta['token']}
            )

    def lot(self, response):
        json_data = json.loads(response.text).get('data', {}).get('lots', {})
        for lot in json_data:
            product = {
                'title': lot.get('title', ''),
                'lot_number': lot.get('lot_number', ''),
                'lot_URL': f'https://bid.madcheetah.com/lots/{lot.get("id", "")}',
                'scheduled end time': datetime.fromtimestamp(lot.get('end_time', '') / 1000).strftime(
                    "%Y-%m-%d %I:%M:%S"),
                'auction_location': lot.get('location_display_name', '')
            }
            yield Request(
                url=f'https://www.google.com/search?q=X{product["title"]}',
                headers=self.headers,
                callback=self.parse_amazon_link,
                meta={'product': product}
            )

    def parse_amazon_link(self, response):
        amazon_url = response.css('[role="main"] [href*="amazon"]::attr(href)').get()
        if amazon_url:
            yield Request(url=amazon_url,
                          callback=self.parse_price,
                          meta={'product': response.meta['product']})

    def parse_price(self, response):
        product = response.meta['product']
        price_string = response.css('.priceToPay .a-offscreen::text').get('0')
        price_value = ''.join(re.findall(r"[-+]?(?:\d*\.\d+|\d+)", price_string))
        if float(price_value) > 200:
            product['Amazon Price'] = price_value
            product['Amazon Link'] = response.url
            yield product
