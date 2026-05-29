"""
Task 1 - SauceDemo UI Automation
=================================
Senior Manual QA perspective | Python + Selenium WebDriver
Target: https://www.saucedemo.com/

Test flow:
  1. Verify the login page is displayed (URL, title, login form presence)
  2. Log in as standard_user
  3. Sort products by Price (low to high) and verify actual sort order
  4. Add the three cheapest items to the cart
  5. Open cart and verify badge count + items + prices match inventory
  6. Proceed to checkout, fill form, verify subtotal = sum of item prices

Credentials: username=standard_user | password=secret_sauce
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC


# ---------------------------------------------------------------------------
# Page Objects
# ---------------------------------------------------------------------------

class LoginPage:
    URL = "https://www.saucedemo.com/"

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    def open(self):
        self.driver.get(self.URL)

    # -- Locators --
    def username_field(self):
        return self.wait.until(EC.visibility_of_element_located((By.ID, "user-name")))

    def password_field(self):
        return self.wait.until(EC.visibility_of_element_located((By.ID, "password")))

    def login_button(self):
        return self.wait.until(EC.element_to_be_clickable((By.ID, "login-button")))

    def login_form(self):
        return self.wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "login_wrapper")))

    # -- Actions --
    def login(self, username, password):
        self.username_field().clear()
        self.username_field().send_keys(username)
        self.password_field().clear()
        self.password_field().send_keys(password)
        self.login_button().click()


class InventoryPage:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    # -- Locators --
    def sort_dropdown(self):
        return self.wait.until(EC.visibility_of_element_located(
            (By.CLASS_NAME, "product_sort_container")
        ))

    def product_prices(self):
        """Return list of float prices currently displayed."""
        price_elements = self.driver.find_elements(By.CLASS_NAME, "inventory_item_price")
        return [float(el.text.replace("$", "")) for el in price_elements]

    def product_names(self):
        name_elements = self.driver.find_elements(By.CLASS_NAME, "inventory_item_name")
        return [el.text for el in name_elements]

    def add_to_cart_buttons(self):
        return self.driver.find_elements(By.XPATH,
            "//button[contains(@class,'btn_inventory') and contains(text(),'Add to cart')]"
        )

    def cart_badge(self):
        return self.wait.until(EC.visibility_of_element_located(
            (By.CLASS_NAME, "shopping_cart_badge")
        ))

    def cart_icon(self):
        return self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "shopping_cart_link")))

    # -- Actions --
    def sort_by_price_low_to_high(self):
        select = Select(self.sort_dropdown())
        select.select_by_value("lohi")

    def add_cheapest_three_to_cart(self):
        """
        After sorting low-to-high the first three items are the cheapest.
        Returns a dict {name: price} for the three items added.
        """
        added = {}
        prices = self.product_prices()
        names  = self.product_names()
        buttons = self.add_to_cart_buttons()

        # The page is already sorted low-to-high; take the first 3
        for i in range(3):
            added[names[i]] = prices[i]
            buttons[i].click()
        return added

    def go_to_cart(self):
        self.cart_icon().click()


class CartPage:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    # -- Locators --
    def cart_items(self):
        return self.driver.find_elements(By.CLASS_NAME, "cart_item")

    def item_names(self):
        return [el.text for el in self.driver.find_elements(By.CLASS_NAME, "inventory_item_name")]

    def item_prices(self):
        return [float(el.text.replace("$", ""))
                for el in self.driver.find_elements(By.CLASS_NAME, "inventory_item_price")]

    def checkout_button(self):
        return self.wait.until(EC.element_to_be_clickable((By.ID, "checkout")))

    # -- Actions --
    def proceed_to_checkout(self):
        self.checkout_button().click()


class CheckoutPage:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    # -- Locators --
    def first_name_field(self):
        return self.wait.until(EC.visibility_of_element_located((By.ID, "first-name")))

    def last_name_field(self):
        return self.wait.until(EC.visibility_of_element_located((By.ID, "last-name")))

    def postal_code_field(self):
        return self.wait.until(EC.visibility_of_element_located((By.ID, "postal-code")))

    def continue_button(self):
        return self.wait.until(EC.element_to_be_clickable((By.ID, "continue")))

    def subtotal_label(self):
        return self.wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "summary_subtotal_label")))

    # -- Actions --
    def fill_form(self, first_name, last_name, postal_code):
        self.first_name_field().send_keys(first_name)
        self.last_name_field().send_keys(last_name)
        self.postal_code_field().send_keys(postal_code)
        self.continue_button().click()

    def get_subtotal(self):
        """Returns the subtotal as a float (strips 'Item total: $')."""
        label_text = self.subtotal_label().text        # e.g. "Item total: $17.97"
        return float(label_text.split("$")[1])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def build_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_saucedemo_checkout():
    driver = build_driver(headless=False)   # set True for headless run
    passed = True

    try:
        # ------------------------------------------------------------------ #
        # Step 1: Verify login page
        # ------------------------------------------------------------------ #
        login_page = LoginPage(driver)
        login_page.open()

        assert driver.current_url == LoginPage.URL, \
            f"[FAIL] Expected URL '{LoginPage.URL}', got '{driver.current_url}'"

        assert "Swag Labs" in driver.title, \
            f"[FAIL] Expected 'Swag Labs' in page title, got '{driver.title}'"

        login_page.login_form()  # raises TimeoutException if form is missing
        print("[PASS] Step 1 - Login page verified (URL, title, form present)")

        # ------------------------------------------------------------------ #
        # Step 2: Log in
        # ------------------------------------------------------------------ #
        login_page.login("standard_user", "secret_sauce")

        inventory_page = InventoryPage(driver)
        WebDriverWait(driver, 10).until(EC.url_contains("inventory"))
        assert "inventory" in driver.current_url, \
            "[FAIL] Login did not navigate to the inventory page"
        print("[PASS] Step 2 - Logged in successfully")

        # ------------------------------------------------------------------ #
        # Step 3: Sort by Price (low to high) and verify order
        # ------------------------------------------------------------------ #
        inventory_page.sort_by_price_low_to_high()

        # Small explicit wait for DOM re-render after sort
        WebDriverWait(driver, 5).until(
            lambda d: len(d.find_elements(By.CLASS_NAME, "inventory_item_price")) > 0
        )

        prices_after_sort = inventory_page.product_prices()
        assert prices_after_sort == sorted(prices_after_sort), \
            f"[FAIL] Products are NOT sorted low-to-high. Prices: {prices_after_sort}"
        print(f"[PASS] Step 3 - Products sorted low-to-high: {prices_after_sort}")

        # ------------------------------------------------------------------ #
        # Step 4: Add the three cheapest items to the cart
        # ------------------------------------------------------------------ #
        added_items = inventory_page.add_cheapest_three_to_cart()
        print(f"[PASS] Step 4 - Added to cart: {added_items}")

        # ------------------------------------------------------------------ #
        # Step 5: Verify cart badge count and cart contents
        # ------------------------------------------------------------------ #
        badge_count = int(inventory_page.cart_badge().text)
        assert badge_count == 3, \
            f"[FAIL] Cart badge shows {badge_count}, expected 3"
        print(f"[PASS] Step 5a - Cart badge count is correct: {badge_count}")

        inventory_page.go_to_cart()
        cart_page = CartPage(driver)

        cart_names  = cart_page.item_names()
        cart_prices = cart_page.item_prices()

        assert len(cart_page.cart_items()) == 3, \
            f"[FAIL] Cart has {len(cart_page.cart_items())} items, expected 3"

        for name, price in added_items.items():
            assert name in cart_names, \
                f"[FAIL] '{name}' was added but is NOT in the cart"
            assert price in cart_prices, \
                f"[FAIL] Price ${price} for '{name}' does not match cart price"

        print(f"[PASS] Step 5b - Cart items and prices match inventory")

        # ------------------------------------------------------------------ #
        # Step 6: Checkout - fill form and verify subtotal
        # ------------------------------------------------------------------ #
        cart_page.proceed_to_checkout()

        checkout_page = CheckoutPage(driver)
        checkout_page.fill_form("Test", "User", "12345")

        expected_subtotal = round(sum(added_items.values()), 2)
        actual_subtotal   = checkout_page.get_subtotal()

        assert actual_subtotal == expected_subtotal, \
            (f"[FAIL] Subtotal mismatch: displayed ${actual_subtotal} "
             f"but expected ${expected_subtotal} (sum of {list(added_items.values())})")

        print(f"[PASS] Step 6 - Checkout subtotal correct: ${actual_subtotal} "
              f"(expected ${expected_subtotal})")

        print("\n=== ALL STEPS PASSED ===")

    except AssertionError as e:
        print(f"\n{e}")
        passed = False

    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        passed = False

    finally:
        driver.quit()
        if not passed:
            raise SystemExit(1)


if __name__ == "__main__":
    test_saucedemo_checkout()
