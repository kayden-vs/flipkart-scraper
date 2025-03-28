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


class ProductsSpider(scrapy.Spider):
    name = "products"
    allowed_domains = ["flipkart.com", "pricehistory.app"]
    
    def start_requests(self):
        start_urls = search_terms.searchTerms  #edited
        base_url = "https://www.flipkart.com/search?q={}&page={}"
        for term in search_terms.searchTerms: #edited
            for page in range(1,26):
                url = base_url.format(term, page)
                yield scrapy.Request(url=url, callback=self.parse)

    def extractValue(self, discount_text):
        match = re.search(r"(\d+)%", discount_text)
        if match:
            discount_value = int(match.group(1))
            return discount_value
        return 0


    def parse(self, response):
        self.logger.info("Scraping URL: %s", response.url)
        for productArea in response.css("div.hCKiGj"):
            product_link = productArea.css("a:first-of-type::attr(href)").get()
            discount_text = productArea.css("div.UkUFwK > span::text").get()
            price = productArea.css("div.hCKiGj > a:nth-of-type(2) > div.hl05eU > div.Nx9bqj::text").get()
            price = price.replace("\u20b9", "").strip()
            discount_value = self.extractValue(discount_text)
            if discount_value > 70:
                full_product_url = f"https://flipkart.com{product_link}"
                yield SeleniumRequest(
                    url="https://pricehistory.app",
                    callback=self.parse_pricetracker,
                    meta={
                        "product": {
                            "discount": discount_text,
                            "price": price,
                            "product_link": full_product_url,
                        },
                        "flipkart_product_url": full_product_url,
                    },
                    wait_time=5
                )
    
    def parse_pricetracker(self, response):
        product = response.meta["product"]
        driver = response.meta['driver']

        search_box = driver.find_element("css selector", "#search")
        search_box.clear()
        search_box.send_keys(response.meta["flipkart_product_url"])
        search_box.submit()

        time.sleep(5)

        #condition 1: product not found
        try:
            wait = WebDriverWait(driver, 10)
            wait.until(EC.any_of(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.p-1.text-white-50.rounded.text-center"))
            ))
        except Exception as e:
            self.logger.error("Timeout waiting for pricetracker page to load: %s", e)
            return
        
        not_found_element = driver.find_elements("css selector", "div.p-1.text-white-50.rounded.text-center")
        if not_found_element:
            self.logger.info("Product not found on pricetracker. Skipping: %s", response.meta["flipkart_product_url"])
            return
        
        #condition 2: product result is shown
        try:
            rating_scale = driver.find_element("css selector", "div.rating-scale.row > div.active").text
            if rating_scale in ["Okay", "Yes"]:
                yield product
            else:
                self.logger.info("Didnt Pass rating scale. Skipping: %s", response.meta["flipkart_product_url"])
        except Exception as e:
            self.logger.error("Error getting the rating scale information: %s", e)