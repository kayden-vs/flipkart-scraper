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
import logging
#avoiding too much logging
logging.getLogger("selenium.webdriver.remote.remote_connection").setLevel(logging.WARNING)

class ProductsSpider(scrapy.Spider):
    name = "products"
    allowed_domains = ["flipkart.com", "pricehistory.app"]
    
    def start_requests(self):
        start_urls = search_terms.searchTerms  
        base_url = "https://www.flipkart.com/search?q={}&page={}"          
        for term in search_terms.searchTerms: 
            for page in range(1,26):
                url = base_url.format(page)                                 
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
        for productArea in response.css("div.hCKiGj"):
            product_link = productArea.css("a:first-of-type::attr(href)").get()
            discount_text = productArea.css("div.UkUFwK > span::text").get()
            price = productArea.css("div.hCKiGj > a:nth-of-type(2) > div.hl05eU > div.Nx9bqj::text").get()
            price = price.replace("\u20b9", "").strip()
            discount_value = self.extractValue(discount_text)
            if discount_value > 75:
                full_product_url = f"https://flipkart.com{product_link}"
                #logging if a product is found
                self.logger.info(f"Found a product with discount value: {discount_value}")
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
                    wait_time=5,
                    dont_filter=True
                )
    
    def parse_pricetracker(self, response):
        product = response.meta["product"]
        driver = response.meta['driver']

        #logging url
        # self.logger.info("flipkart_product_url: %s", response.meta.get("flipkart_product_url"))
        wait = WebDriverWait(driver, 10)
        search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#search")))
        search_box = driver.find_element(By.CSS_SELECTOR, "#search")
        search_box.clear()
        search_box.send_keys(response.meta["flipkart_product_url"])
        self.logger.info("Typed URL in search box: %s", search_box.get_attribute("value"))
        # search_button = driver.find_element(By.CSS_SELECTOR, "#search-submit")
        # search_button.click()
        search_box.send_keys(Keys.ENTER)

        time.sleep(10)
        #for debugging
        self.logger.info("Current URL after search submission: %s", driver.current_url)
        driver.save_screenshot("after_search.png")
        self.logger.info("Saved screenshot to after_search.png")
        #condition 1: product not found
        try:
            wait = WebDriverWait(driver, 10)
            wait.until(EC.any_of(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.p-1.text-white-50.rounded.text-center"))
            ))
        except Exception as e:
            self.logger.error("Timeout waiting for pricetracker page to load: %s", e)
            return
        
        not_found_elements = driver.find_elements(By.CSS_SELECTOR, "div.p-1.text-white-50.rounded.text-center")
        if not_found_elements and any("Page not Found!" or "Product Added to Track!" in el.text for el in not_found_elements):
            self.logger.info("Product not found on pricetracker. Skipping: %s", response.meta["flipkart_product_url"])
            return
        
        #condition 2: product result is shown
        try:
            rating_scale = driver.find_element(By.CSS_SELECTOR, "div.rating-scale.row > div.active").text
            if rating_scale in ["Okay", "Yes"]:
                yield product
            else:
                self.logger.info("Didnt Pass rating scale. Skipping: %s", response.meta["flipkart_product_url"])
        except Exception as e:
            self.logger.error("Error getting the rating scale information: %s", e)