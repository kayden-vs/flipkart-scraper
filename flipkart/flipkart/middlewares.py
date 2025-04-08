# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
import random
import re
# from selenium.webdriver.chrome.service import Service
# from selenium import webdriver
from fake_useragent import UserAgent

# useful for handling different item types with a single interface
from itemadapter import is_item, ItemAdapter


class FlipkartSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.
    # USER_AGENTS = [
    #     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36",
    #     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15",
    #     # Add additional user agent strings as needed
    # ]

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)

class FlipkartDownloaderMiddleware:
    def __init__(self):
        # Initialize with specific browsers that support sec-ch-ua headers well
        self.ua = UserAgent(browsers=['Chrome', 'Firefox', 'Edge'])

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        ua_dict = self.ua.getRandom
        request.headers["User-Agent"] = ua_dict['useragent']
        request.headers.pop("X-Forwarded-For", None)
        
        if 'pricehistory.app' in request.url:
            # Apply longer timeout for this domain
            domain_timeout = spider.settings.get('DOWNLOAD_TIMEOUTS', {}).get('pricehistory.app')
            if domain_timeout:
                request.meta['download_timeout'] = domain_timeout
            
            request.meta['download_delay'] = 3.0
            
            # Important - add Origin header (missing in your current code)
            request.headers["Origin"] = "https://pricehistory.app"
            request.headers["Accept"] = "application/json, text/plain, */*"
            
            # Existing headers
            request.meta['cookiejar'] = 'pricehistory'
            request.headers["DNT"] = "1"
            request.headers["Content-Type"] = "application/json"
            request.headers["Referer"] = "https://pricehistory.app/"
            request.headers["Accept-Language"] = "en-US,en;q=0.9"
            
            # Extract browser information
            browser = ua_dict['browser']
            version = ua_dict['browser_version_major_minor']
            os_name = ua_dict['os']
            device_type = ua_dict['type']
            
            # Set mobile flag based on device type
            is_mobile = device_type == 'mobile'
            request.headers["Sec-Ch-Ua-Mobile"] = "?1" if is_mobile else "?0"
            
            # Set platform based on OS
            request.headers["Sec-Ch-Ua-Platform"] = f'"{os_name}"'
            
            # Set browser-specific sec-ch-ua header
            if browser == 'Chrome':
                request.headers["Sec-Ch-Ua"] = f'"Chromium";v="{int(version)}", "Not:A-Brand";v="24", "Google Chrome";v="{int(version)}"'
                
            elif browser == 'Firefox':
                request.headers["Sec-Ch-Ua"] = f'"Firefox";v="{int(version)}"'
                
            elif browser == 'Edge':
                request.headers["Sec-Ch-Ua"] = f'"Microsoft Edge";v="{int(version)}", "Chromium";v="{int(version)}"'
            
            # Add additional headers for more realistic browser fingerprint
            request.headers["Sec-Fetch-Dest"] = "empty"
            request.headers["Sec-Fetch-Mode"] = "cors"
            request.headers["Sec-Fetch-Site"] = "same-origin"
            
        return None
    
    def process_response(self, request, response, spider):
        return response

    def process_exception(self, request, exception, spider):
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)