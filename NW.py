import time
import csv
import re
import random
from datetime import datetime
from fake_useragent import UserAgent
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import pandas as pd

HEADLESS = False
RETRY_WAIT = 600  # 10 minutes
MAX_WAIT = 3600   # 60 minutes

departments = [
    'pantry','fresh-foods-and-bakery', 'baby-toddler-and-kids', 'beer-cider-and-wine', 'chilled-frozen-and-desserts', 'drinks', 'household-and-cleaning', 'hot-and-cold-drinks'
]

today = datetime.now().strftime("%Y%m%d")
output_file = f"{today}-NWPrices.csv"

script_start = time.time()

ua = UserAgent()

def create_browser():
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={ua.random}")
    if HEADLESS:
        options.headless = True
    return uc.Chrome(options=options)

driver = create_browser()

changed = 0


with open(output_file, mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(['date', 'name', 'subtitle', 'promo_price', 'regular_price', 'unit', 'department','sku'])

    for dept in departments:
        page = 1
        while True:
            url = f"https://www.newworld.co.nz/shop/category/{dept}?pg={page}"
           
            
            print(f"\nFetching: {url}")
            driver.get(url)
            if changed != 1:
                try:
                    store_name = driver.find_element(By.CSS_SELECTOR, 'p[data-testid="choose-store"]')
                    print(store_name.text.strip())
                    if store_name.text.strip() == "New World Victoria Park":
                        changed = 1                        
                        continue
                    else:
                        change_btn = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-testid="tooltip-choose-store"]'))
                        )
                        driver.execute_script("arguments[0].click();", change_btn)
                        
                        
                        store_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, 'input[placeholder="Search by store name, city or town/suburb"]')
                            )
                        )
                        store_input.clear()
                        store_input.send_keys("New World Victoria Park")
                        store_option = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//p[text()='New World Victoria Park']"))
                        )
                        driver.execute_script("arguments[0].click();", store_option)

                        driver.get(url)                    
                except NoSuchElementException:
                    continue

            if "You are being rate limited" in driver.page_source:
                print("Cloudflare rate limit hit. Waiting and retrying...")
                wait_intervals = [60, 300, 300, 600] 
                for wait_time in wait_intervals:
                    print(f"Waiting {wait_time // 60} minutes before retry...")
                    time.sleep(wait_time)
                    driver.quit()
                    driver = create_browser()
                    changed = 0
                    driver.get(url)
                    if "You are being rate limited" not in driver.page_source:
                        break
                else:
                    print(f"Still blocked after 60 minutes. Last attempted URL: {url}")
                    break

            if "Sorry, we couldn’t find any products" in driver.page_source:
                print(f"No more results in department: {dept}")
                break

            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid^="product-"]'))
                )
            except TimeoutException:
                print(f"Timeout waiting for products on page {page}. Skipping.")
                page += 1
                continue

            products = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid^="product-"]')
            if not products:
                print(f"No products found on page {page} in {dept}")
                break

            for product in products:
                try:
                    # Extract SKU
                    data_testid = product.get_attribute("data-testid")
                    match = re.search(r"product-(\d+)-", data_testid)
                    sku = match.group(1) if match else ""

                    try:
                        name = product.find_element(By.CSS_SELECTOR, 'p[data-testid="product-title"]').text.strip()
                    except:
                        name = ""
                        

                    try:
                        subtitle = product.find_element(By.CSS_SELECTOR, 'p[data-testid="product-subtitle"]').text.strip()
                    except:
                        subtitle = ""

                    # Extract unit price
                    try:
                        unit = product.find_element(By.CSS_SELECTOR, 'p[data-testid="price-per"]').text.strip()
                    except:
                        unit = ""

                    try:
                        price_container = product.find_element(By.CSS_SELECTOR, 'div[data-testid="price"]')
                        regular_dollars = price_container.find_element(By.CSS_SELECTOR, 'p[data-testid="price-dollars"]').text.strip()
                        regular_cents = price_container.find_element(By.CSS_SELECTOR, 'p[data-testid="price-cents"]').text.strip()
                        regular_price = f"{regular_dollars}.{regular_cents}"
                    except NoSuchElementException:
                        regular_price = ""

                    # Promo
                    try:
                        decal_price_container = product.find_element(By.CSS_SELECTOR, 'div[data-testid="decal-price"]')
                        promo_dollars = decal_price_container.find_element(By.CSS_SELECTOR, 'p[data-testid="price-dollars"]').text.strip()
                        promo_cents = decal_price_container.find_element(By.CSS_SELECTOR, 'p[data-testid="price-cents"]').text.strip()
                        promo_price = f"{promo_dollars}{promo_cents}"
                    except:
                        promo_price = ""

                    writer.writerow([today, name, subtitle, promo_price, regular_price, unit, dept, sku])

                except Exception as e:
                    print(f"Error extracting product: {e}")
                    print(product.get_attribute("outerHTML"))
                    continue
            page += 1
                

driver.quit()

df = pd.read_csv(output_file)
df_cleaned = df[df['name'].notna() & (df['name'].astype(str).str.strip() != '')]
df_cleaned.to_csv(output_file, index=False)

elapsed = time.time() - script_start
mins, secs = divmod(int(elapsed), 60)
print(f"\nScraping complete. File saved: {output_file}")
print(f"Total time: {mins} minutes, {secs} seconds")

