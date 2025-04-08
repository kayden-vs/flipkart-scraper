import scrapy
import re
import json
import requests
from . import search_terms
import time
from .telegram_utils import send_telegram_message
import logging
import os
from dotenv import load_dotenv
from twisted.internet.error import TimeoutError, ConnectionRefusedError
from scrapy.spidermiddlewares.httperror import HttpError

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
class ProductsSpider(scrapy.Spider):
    name = "products"
    allowed_domains = ["flipkart.com", "pricehistory.app"]
    
    def start_requests(self):
        import random
        terms = list(search_terms.footwear)
        random.shuffle(terms)  # Randomize search term order
        
        # Only request the first page of each search term initially
        for term in terms:
            url = f"https://www.flipkart.com/search?q={term}&page=1"
            yield scrapy.Request(
                url=url,
                callback=self.parse,
                meta={"search_term": term, "current_page": 1}
            )

    def extractValue(self, discount_text):
        if not discount_text:
            return 0
        match = re.search(r"(\d+)%", discount_text)
        if match:
            discount_value = int(match.group(1))
            return discount_value
        return 0

    def parse(self, response):
        self.logger.info("Scraping URL: %s", response.url)
        # Log an excerpt of the HTML to see if the page source is as expected
        # self.logger.info("Response excerpt:\n%s", response.text[:1000])

        #handles different page layouts
        product_areas = response.css("div.hCKiGj")
        layout = 'first'
        if not product_areas:
            product_areas = response.css("div.slAVV4")
            if product_areas:
                layout = 'second'
            else:
                product_areas = response.css("div.tUxRFH")
                if product_areas:
                    layout = 'third'


        for productArea in product_areas:
            product_link = productArea.css("a:first-of-type::attr(href)").get()
            discount_text = productArea.css("div.UkUFwK > span::text").get()

            if layout == 'first':
                title = productArea.css("a.WKTcLC::attr(title)").get()
                price = productArea.css("div.Nx9bqj::text").get()
            elif layout == 'second':
                title = productArea.css("a.wjcEIp::attr(title)").get()
                price = productArea.css("div.Nx9bqj::text").get()
            elif layout == 'third':
                title = productArea.css("div.KzDlHZ").get()
                price = productArea.css("div.Nx9bqj::text").get()

            if price:
                price = price.replace("\u20b9", "").strip()
            else:
                self.logger.error("Price not found for product: %s", title)
                continue
        
            discount_value = self.extractValue(discount_text)
            if discount_value > 75:
                full_product_url = f"https://www.flipkart.com{product_link}"
                self.logger.info(f"FOUND : {title}: Rs.{price} ({discount_value}% Off)")

                # for API search requests
                yield scrapy.Request(
                    url="https://pricehistory.app/api/search",
                    method='POST',
                    body=json.dumps({"url": full_product_url}),
                    callback=self.parse_price_search_result,
                    errback=self.handle_error,
                    meta={
                        "product": {
                            "title": title,
                            "discount": discount_text,
                            "price": price,
                            "product_link": full_product_url,
                        }
                    },
                    dont_filter=True,
                    priority=10
                )
        
        # At the end of your parse method, add:
        search_term = response.meta.get("search_term")
        current_page = response.meta.get("current_page", 1)
        
        # Request next page only after processing current page
        if current_page < 25:
            next_page = current_page + 1
            next_url = f"https://www.flipkart.com/search?q={search_term}&page={next_page}"
            yield scrapy.Request(
                url=next_url,
                callback=self.parse,
                meta={"search_term": search_term, "current_page": next_page},
                priority=-1  #lowest priority
            )

    def parse_price_search_result(self, response):

        #for debugging
        # self.logger.info(f"Status: {response.status}, URL: {response.url}")
        # self.logger.info(f"Headers: {response.headers}")
        # self.logger.info(f"Body: {response.text[:200]}")
        product = response.meta['product']
        
        try:
            data = json.loads(response.text)
            if (data.get('status') == 'true' or data.get('status') is True) and data.get('code'):
                self.logger.info(f"Product found on Pricetracker: {product['title']}")
                url_code = data['code']
                
                # Add debug log before making request
                self.logger.debug(f"Making request to https://pricehistory.app/p/{url_code}")
                
                # Make request to the product page to get price history
                yield scrapy.Request(
                    url=f"https://pricehistory.app/p/{url_code}",
                    callback=self.parse_price_history,
                    errback=self.handle_error,
                    meta={"product": product},
                    dont_filter=True,
                    priority=20
                )
            else:
                self.logger.info(f"Product not on Pricetracker: {product['title']}")
        except json.JSONDecodeError:
            self.logger.error(f"Failed to decode JSON response: {response.text[:100]}")
        except Exception as e:
            self.logger.error(f"Error processing price search result: {str(e)}")

    def parse_price_history(self, response):
        # Add debug log at the beginning of the method
        self.logger.debug(f"Successfully reached price history page: {response.url}")
        
        product = response.meta['product']
        flipkart_product_url = product.get('product_link')

        try:
            # Fix the logical error in rating check
            rating_scale = response.css("div.rating-scale > div.active::text").get()
            if rating_scale in ["Okay", "Yes"]:  # Correct way to check if value is in a list
                message = (
                    f"<b>Product Found!</b>\n"
                    f"Title: {product.get('title')}\n"
                    f"Discount: {product.get('discount')}\n"
                    f"Price: {product.get('price')}\n"
                    f"Rating Scale: {rating_scale}\n" 
                    f"Link: <a href='{product.get('product_link')}'>{product.get('product_link')}</a>"
                )
                send_telegram_message(message, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
                yield product
            else:
                self.logger.info(f"Didn't pass rating scale ({rating_scale}). Skipping: {product.get('title')}")
        except Exception as e:
            self.logger.error(f"Error getting rating scale info: {str(e)}")

    def handle_error(self, failure):
        request = failure.request
        product = request.meta.get('product', {})
        
        if failure.check(HttpError):
            response = failure.value.response
            if response.status == 404:
                self.logger.info(f"Product not found on Pricetracker: {product.get('title', 'Unknown')}")
            else:
                self.logger.error(f"HTTP Error {response.status} for {product.get('title', 'Unknown')}")
        elif failure.check(TimeoutError, ConnectionRefusedError):
            self.logger.warning(f"Connection error for {product.get('title', 'Unknown')} - retrying")
            # Create a new request with increased delay
            new_request = request.copy()
            new_request.meta['download_delay'] = 5.0
            new_request.dont_filter = True
            return new_request
        else:
            self.logger.error(f"Error for {product.get('title', 'Unknown')}: {repr(failure.value)}")


