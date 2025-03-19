from /home/rohit/Desktop/Projects/scrapers/flipkart/flipkart/spiders/products.py import search_terms as search

#get the page links
search_term = "shoes"
pages = []
for page in range(1,10): 
    pages.append(f"https://www.flipkart.com/search?q={search_term}&page={page}");

for term in search.searchTerms:
    print(term)
