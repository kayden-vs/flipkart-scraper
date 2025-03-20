import scrapy
import re
import search_terms
import random
import time

class ProducsSpider(scrapy.Spider):
    name = "ptroducts"
    allowed_domains = ["flipkart.com"]
    
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
            discount_value = self.extractValue(discount_text)
            if discount_value > 70:                             #discount here
                yield {
                    "discount": discount_text,
                    "product-link": f"https://flipkart.com{product_link}",
                }