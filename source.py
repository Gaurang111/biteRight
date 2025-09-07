import requests
from PIL import Image
from pyzbar.pyzbar import decode as zbar_decode

def decode_barcode_from_image(image_path: str):
    img = Image.open(image_path)
    codes = zbar_decode(img)
    preferred = {"EAN13", "EAN8", "UPCA", "UPCE"}
    for c in codes:
        if c.type in preferred:
            return c.data.decode("utf-8").strip()
    return None

def openfoodfacts_by_gtin(gtin: str):

    url = f"https://world.openfoodfacts.org/api/v3/product/{gtin}"
    r = requests.get(url, params={"fields": ",".join([
        "product_name","brands",
        "image_url","image_front_url","image_nutrition_url",
        "ingredients_text","nutriments","serving_size"])}, timeout=12)

    if r.status_code != 200:
        return None
    j = r.json()
    if j.get("status") != "success" or "product" not in j:
        return None
    prod = j["product"]
    if not prod:
        return None
    name = (prod.get("product_name") or "").strip()
    brands = (prod.get("brands") or "").strip()
    ingredients_text = (prod.get("ingredients_text") or "").strip()
    nutriments = (prod.get("nutriments") or "")
    image_front_url = (prod.get("image_front_url") or "").strip()
    image_nutri_url = (prod.get("image_nutrition_url") or "").strip()
    serving_size = (prod.get("serving_size") or "").strip()

    return {
        "source": "OpenFoodFacts",
        "product_name": name or None,
        "brand": brands.split(",")[0].strip() if brands else None,
        "ingredients_text": ingredients_text or None,
        "nutriments": nutriments or None,
        "image_front_url": image_front_url or None,
        "image_nutri_url": image_nutri_url or None,
        "serving_size": serving_size or None,
    }

def reconcile(gtin: str) -> dict:
    chosen = openfoodfacts_by_gtin(gtin)
    return chosen
