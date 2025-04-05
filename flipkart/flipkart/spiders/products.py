import scrapy
import re
from scrapy_selenium import SeleniumRequest
from . import search_terms
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from .telegram_utils import send_telegram_message
import logging
import os
from dotenv import load_dotenv
#avoiding too much logging
logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
class ProductsSpider(scrapy.Spider):
    name = "products"
    allowed_domains = ["flipkart.com", "pricehistory.app"]
    
    def start_requests(self):
        start_urls = search_terms.fashion_and_apparel  #edited
        base_url = "https://www.flipkart.com/search?q={}&page={}"          
        for term in search_terms.fashion_and_apparel:   #edited
            for page in range(1,26):
                url = base_url.format(term, page)                                 
                yield scrapy.Request(url=url, callback=self.parse)          

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
                full_product_url = f"https://flipkart.com{product_link}"
                #logging if a product is found
                self.logger.info(f"FOUND : {title}: Rs.{price} ({discount_value}% Off)")
                yield SeleniumRequest(
                    url="https://pricehistory.app",
                    callback=self.parse_pricetracker,
                    meta={
                        "product": {
                            "title": title,
                            "discount": discount_text,
                            "price": price,
                            "product_link": full_product_url,
                        },
                        "flipkart_product_url": full_product_url,
                    },
                    wait_time=5,
                    dont_filter=True  #changed
                )
    
    def parse_pricetracker(self, response):
        product = response.meta["product"]
        driver = response.meta['driver']

        # self.logger.info("flipkart_product_url: %s", response.meta.get("flipkart_product_url"))
        wait = WebDriverWait(driver, 10)
        search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#search")))
        search_box = driver.find_element(By.CSS_SELECTOR, "#search")
        search_box.clear()
        search_box.send_keys(response.meta["flipkart_product_url"])
        self.logger.info("Typed URL in search box: %s", search_box.get_attribute("value"))
        search_box.send_keys(Keys.ENTER)
        time.sleep(10)

        #for debugging
        # self.logger.info("Current URL after search submission: %s", driver.current_url)
        driver.save_screenshot("after_search.png")
        self.logger.info("Saved screenshot to after_search.png")

        #condition 1: product not found
        # try:
        #     wait = WebDriverWait(driver, 10)
        #     wait.until(EC.any_of(
        #         EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.p-1.text-white-50.rounded.text-center"))
        #     ))
        # except Exception as e:
        #     self.logger.error("Timeout waiting for pricetracker page to load: %s", e)
        #     return
        
        # not_found_elements = driver.find_elements(By.CSS_SELECTOR, "div.p-1.text-white-50.rounded.text-center")
        # if not_found_elements and any(
        #     msg in el.text for el in not_found_elements for msg in [
        #         "Page not Found!",
        #         "Product Added to Track!",
        #         "Store Not Supported as of Now!"
        #     ]
        # ):
        #     self.logger.info(
        #         "Product not found on pricetracker. Skipping: %s",
        #         response.meta["flipkart_product_url"]
        #     )
        #     return
        
        #condition 2: product result is shown
        try:
            rating_scale_el = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.rating-scale.row > div.active"))
            )
            rating_scale = rating_scale_el.text.strip()
            self.logger.info("Rating scale text obtained: '%s'", rating_scale)
            if rating_scale in ["Okay", "Yes"]:
                #send telegram notification
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
                self.logger.info("Didnt Pass rating scale. Skipping: %s", response.meta["flipkart_product_url"])
        except Exception as e:
            self.logger.error("Product not in Pricetracker: %s", product.get('title'))  #replaced this selenium error