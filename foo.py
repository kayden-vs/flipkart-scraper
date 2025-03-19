import requests
from bs4 import BeautifulSoup

url = "https://www.flipkart.com/search"

querystring = {"q":"shoes","as":"on","as-show":"on","otracker":"AS_Query_TrendingAutoSuggest_2_0_na_na_na","otracker1":"AS_Query_TrendingAutoSuggest_2_0_na_na_na","as-pos":"2","as-type":"TRENDING","suggestionId":"shoes","requestId":"f88751ab-bca7-4ac8-9db6-d18c46c2f2ad"}

headers = {}

response = requests.request("GET", url, headers=headers, params=querystring)
soup = BeautifulSoup(response.text, "html.parser")
formatted_html = soup.prettify()

with open("formated-html.html", "w", encoding="utf-8") as file:
    file.write(formatted_html)

print("HTML response saved successfully!")
