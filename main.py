from flask import Flask, render_template, request, redirect, url_for
import uuid
import chromadb
from urllib.parse import urlparse

app = Flask(__name__)
# Connect to your ChromaDB server
chroma_client = chromadb.HttpClient(host='94.72.110.93', port=8000)

# @app.route('/search', methods=['POST'])
# def search_products():
#     data = request.get_json()
#     query = data.get("query", "")
    
#     if not query:
#         return jsonify({"error": "Query is required"}), 400
    
#     # Get product collection
#     collection = chroma_client.get_or_create_collection(name="kids_products_firelabel")
    
#     # Query ChromaDB for matching products
#     query_result = collection.query(query_texts=[query], n_results=21)
    
#     products = []
#     for doc_list in query_result.get('documents', []):  # Iterate over document lists
#         for doc in doc_list:  # Iterate over individual documents
#             product_info = doc.split('\n')  # Split text by new lines
#             if len(product_info) >= 6:  # Ensure expected format
#                 product_data = {
#                     "name": product_info[0].replace("Product: ", "").strip(),
#                     "price": product_info[1].replace("Price: ", "").strip(),
#                     "description": product_info[2].replace("Description: ", "").strip(),
#                     "url": product_info[3].replace("Link: ", "").strip(),
#                     "colors": product_info[4].replace("Colors: ", "").strip(),
#                     "image": product_info[5].replace("Image: ", "").strip()
#                 }
#                 products.append(product_data)

#     reasoning = f"Based on your search for '{query}', we found these relevant products."
    
#     return jsonify({
#         "reasoning": reasoning,
#         "products": products
#     })

# if __name__ == '__main__':
#     app.run(debug=True, host='0.0.0.0', port=5000)




def extract_category(product_link):
    """
    Extracts a category from a product URL.
    For example, given:
    https://www.firelabel.co.uk/childrens/t-shirts/61033-fruit-of-the-loom-kids-value-t-shirt.html
    it returns 't-shirts'.
    """
    parsed = urlparse(product_link)
    # The path is like: /childrens/t-shirts/61033-fruit-of-the-loom-kids-value-t-shirt.html
    parts = parsed.path.split('/')
    if len(parts) > 2:
        return parts[2]
    return "Uncategorized"

# In-memory search history
searches = {}

CATEGORIES = [
    "Featured", "Consumer Electronics", "Apparel & Accessories",
    "Packaging & Printing", "Men's Clothing"
]

@app.route("/")
def home():
    """
    Landing page that fetches products from the 'kids_products_firelabel' collection
    and displays them.
    """
    # Retrieve the collection from ChromaDB
    collection = chroma_client.get_collection("kids_products_firelabel")
    # Assuming the collection.get() returns a dictionary with keys "ids" and "metadatas"
    results = collection.get()
    
    products = []
    category_set=set()
    ids = results.get("ids", [])
    metadatas = results.get("metadatas", [])
    
    for idx, prod_id in enumerate(ids):
        meta = metadatas[idx] if idx < len(metadatas) else {}
        product_link = meta.get("product_link", "")
        category = extract_category(product_link)
        category_set.add(category)
        product = {
            "id": prod_id,
            "colors": meta.get("colors", ""),
            "description": meta.get("description", ""),
            "image": meta.get("image_url", ""),
            "name": meta.get("name", ""),
            "price": meta.get("price", ""),
            "product_link": meta.get("product_link", ""),
            "category": extract_category(meta.get("product_link", ""))
        }
        products.append(product)
    CATEGORIES = sorted(list(category_set))
    return render_template("index.html", categories=CATEGORIES, products=products)

@app.route("/start_search", methods=["POST"])
def start_search():
    """
    Generate a unique chat ID, store the user's query or clicked category,
    and redirect to the search results page.
    """
    query = request.form.get("query", "").strip()
    category = request.form.get("category", "").strip()
    final_query = query if query else category
    chatid = str(uuid.uuid4())[:8]
    collection = chroma_client.get_collection("kids_products_firelabel")
    # Assuming the collection.get() returns a dictionary with keys "ids" and "metadatas"
    results = collection.get()
    
    products = []
    ids = results.get("ids", [])
    metadatas = results.get("metadatas", [])
    
    for idx, prod_id in enumerate(ids):
        meta = metadatas[idx] if idx < len(metadatas) else {}
        product = {
            "id": prod_id,
            "colors": meta.get("colors", ""),
            "description": meta.get("description", ""),
            "image": meta.get("image_url", ""),
            "name": meta.get("name", ""),
            "price": meta.get("price", ""),
            "product_link": meta.get("product_link", ""),
            "category": extract_category(meta.get("product_link", ""))
        }
        products.append(product)
    # For simplicity, we are not filtering the products based on the search query.
    # You can add filtering logic as needed.
    searches[chatid] = {
        "query": final_query,
        "products": products  # Optionally, filter your products here.
    }
    return redirect(url_for("show_chat", chatid=chatid))

@app.route("/<chatid>")
def show_chat(chatid):
    """
    Display the search result page for a specific chat ID with the stored query and products.
    Products are fetched from the 'kids_products_firelabel' collection and filtered
    based on the query (matching product name or category).
    """
    data = searches.get(chatid)
    if not data:
        return "Invalid chat ID", 404

    query = data["query"]

    # Retrieve products from the ChromaDB collection
    collection = chroma_client.get_collection("kids_products_firelabel")
    results = collection.get()
    category_set = set()
    products = []
    ids = results.get("ids", [])
    metadatas = results.get("metadatas", [])
    
    for idx, prod_id in enumerate(ids):
        meta = metadatas[idx] if idx < len(metadatas) else {}
        product_link = meta.get("product_link", "")
        category = extract_category(product_link)
        category_set.add(category)

        product = {
            "id": prod_id,
            "colors": meta.get("colors", ""),
            "description": meta.get("description", ""),
            "image": meta.get("image_url", ""),
            "name": meta.get("name", ""),
            "price": meta.get("price", ""),
            "product_link": product_link,
            "category": category
        }
        products.append(product)
    
    # Filter products based on the stored query:
    # Include products where the query appears in the product name or category.
    if query:
        filtered_products = [
            p for p in products 
            if query.lower() in p["name"].lower() or query.lower() in p["category"].lower()
        ]
    else:
        filtered_products = products

    return render_template("search.html", chatid=chatid,
                           query=query,
                           products=filtered_products)
if __name__ == "__main__":
    app.run(debug=True,host='0.0.0.0',port=5500)