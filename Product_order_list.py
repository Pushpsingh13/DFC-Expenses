import streamlit as st
import pandas as pd
import os
from datetime import datetime
import uuid

# Optional PDF library
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except Exception:
    FPDF_AVAILABLE = False

# -------------------------
# Config / Files
# -------------------------
st.set_page_config(page_title="Product Order System", layout="wide", page_icon="🛒")

PRODUCT_FILE = "product_template.xlsx"
ORDER_FILE = "orders.xlsx"

# -------------------------
# Helpers
# -------------------------
def now_local_str():
    """Return local timezone-aware timestamp string."""
    # datetime.now().astimezone() gives local timezone-aware time
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

def extract_category_from_productlist(s: str) -> str:
    """Try to preserve original category token (like 'Bread_Product' if present)"""
    s = str(s)
    # If product list contains something like Bread_Product_xxx, preserve Bread_Product
    parts = s.split("_")
    if len(parts) >= 2 and parts[0] and parts[1].lower().startswith("product"):
        # unlikely format, fallback below
        pass
    # Try to detect tokens that include 'Product' word, e.g. 'Bread_Product_1_xxx'
    for token in s.split():
        if "Product" in token:
            return token.split("_")[0] + "_Product" if "_" in token else token
    # fallback: return prefix up to first underscore if it contains Product word in original
    if "_" in s:
        first = s.split("_")[0]
        # if original contains "Product" as second token, produce e.g., Bread_Product
        toks = s.split("_")
        if len(toks) >= 2 and toks[1].lower().startswith("product"):
            return f"{toks[0]}_Product"
        return first
    return "General"

def weight_applicable_for_row(prodlist: str) -> bool:
    """Return True if weight input should be shown for the product.
       Excludes Bread_Product and Packing_Product."""
    s = str(prodlist)
    # If the token 'Bread_Product' or 'Packing_Product' appears anywhere -> NO weight
    if "Bread_Product" in s or "Packing_Product" in s:
        return False
    # Also check category token detection
    if "Bread_Product" == extract_category_from_productlist(s) or "Packing_Product" == extract_category_from_productlist(s):
        return False
    return True

# -------------------------
# Load products (NO IMAGES)
# -------------------------
@st.cache_data
def load_products(product_file=PRODUCT_FILE):
    # Create demo file if missing
    if not os.path.exists(product_file):
        example = pd.DataFrame({
            "Product List": [
                "Milk_Product_1_Cheese Mozorella",
                "Milk_Product_2_Butter",
                "Bread_Product_1_Pizza Base 10 inch",
                "Sauces_Product_6_Tomato ketchup",
                "Packing_Product_1_Box Small"
            ],
            "Product Name": ["Cheese Mozorella", "Butter", "Pizza Base 10 inch", "Tomato ketchup", "Box Small"],
            "Supplier": ["Blink IT", "Blink IT", "Baker's Hub", "Sauce Co.", "PackCo"],
            "Price": [535.0, 290.0, 120.0, 60.0, 15.0]
        })
        example.to_excel(product_file, index=False)

    df = pd.read_excel(product_file)

    # Detect product column
    product_col = None
    for col in df.columns:
        vals = df[col].astype(str).str.lower()
        if vals.str.contains("product_").any() or "product" in col.lower():
            product_col = col
            break
    if product_col is None:
        product_col = df.columns[0]

    # Detect name column
    name_col = None
    for col in df.columns:
        if "name" in col.lower():
            name_col = col
            break
    if name_col is None:
        name_col = product_col

    # Supplier & Price
    supplier_col = None
    price_col = None
    for col in df.columns:
        low = col.lower()
        if "supplier" in low:
            supplier_col = col
        if "price" in low or "rate" in low or "cost" in low:
            price_col = col

    if supplier_col is None:
        # pick a sensible default (first non-product/name column)
        possible = [c for c in df.columns if c not in (product_col, name_col)]
        supplier_col = possible[0] if possible else None

    if price_col is None:
        numeric_cols = df.select_dtypes(include=["number"]).columns
        price_col = numeric_cols[0] if len(numeric_cols) else None

    # Build renamed dataframe
    rename_map = {}
    rename_map[product_col] = "ProductList"
    rename_map[name_col] = "Product"
    if supplier_col:
        rename_map[supplier_col] = "Supplier"
    if price_col:
        rename_map[price_col] = "Price"

    df = df.rename(columns=rename_map)

    if "Supplier" not in df.columns:
        df["Supplier"] = ""

    if "Price" not in df.columns:
        df["Price"] = 0.0

    # Category detection (keep token like Bread_Product if present in ProductList)
    def extract_category(x):
        s = str(x)
        # If the product list contains explicit 'Bread_Product' or 'Packing_Product', preserve it
        if "Bread_Product" in s:
            return "Bread_Product"
        if "Packing_Product" in s:
            return "Packing_Product"
        # else, use prefix before first underscore
        if "_" in s:
            return s.split("_")[0]
        return "General"

    df["Category"] = df["ProductList"].apply(extract_category)

    # Price numeric coercion
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0.0)

    return df

df = load_products()

# -------------------------
# Cart & Helpers
# -------------------------
if "cart" not in st.session_state:
    st.session_state.cart = []

def add_to_cart(product, supplier, price, qty, weight_str=""):
    st.session_state.cart.append({
        "OrderID": None,
        "Product": product,
        "Supplier": supplier,
        "Price": float(price),
        "Qty": int(qty),
        "Weight": weight_str,
        "LineTotal": float(price) * int(qty)
    })

def clear_cart():
    st.session_state.cart = []

def compute_cart_totals(discount_pct=0.0):
    dfc = pd.DataFrame(st.session_state.cart) if st.session_state.cart else pd.DataFrame(columns=["LineTotal"])
    subtotal = dfc["LineTotal"].sum() if not dfc.empty else 0.0
    discount_val = subtotal * (discount_pct / 100.0)
    total = subtotal - discount_val
    return subtotal, discount_val, total

def save_order(cart, discount_pct=0.0):
    order_id = str(uuid.uuid4()).split("-")[0].upper()
    now = now_local_str()

    rows = []
    for line in cart:
        row = {
            "OrderID": order_id,
            "Timestamp": now,
            "Product": line["Product"],
            "Supplier": line.get("Supplier", ""),
            "Price": line["Price"],
            "Qty": line["Qty"],
            "Weight": line.get("Weight", ""),
            "LineTotal": line["LineTotal"],
            "DiscountPct": discount_pct
        }
        rows.append(row)

    df_new = pd.DataFrame(rows)

    if os.path.exists(ORDER_FILE):
        df_existing = pd.read_excel(ORDER_FILE)
        df_out = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_out = df_new

    df_out.to_excel(ORDER_FILE, index=False)

    return order_id, df_new

def create_pdf_receipt(order_id, df_order, subtotal, discount_val, total):
    if not FPDF_AVAILABLE:
        return None

    pdf = FPDF(format="A4")
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Receipt - Order {order_id}", ln=True, align="C")
    pdf.cell(200, 6, txt=f"Generated: {now_local_str()}", ln=True)
    pdf.ln(4)

    # Header (include Weight column)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(70, 8, "Product", border=1)
    pdf.cell(25, 8, "Weight", border=1)
    pdf.cell(25, 8, "Price", border=1)
    pdf.cell(15, 8, "Qty", border=1)
    pdf.cell(30, 8, "LineTotal", border=1, ln=True)

    pdf.set_font("Arial", size=11)
    for _, r in df_order.iterrows():
        pdf.cell(70, 8, str(r["Product"])[:30], border=1)
        pdf.cell(25, 8, str(r.get("Weight", ""))[:10], border=1)
        pdf.cell(25, 8, f"₹{r['Price']:.2f}", border=1)
        pdf.cell(15, 8, str(int(r["Qty"])), border=1)
        pdf.cell(30, 8, f"₹{r['LineTotal']:.2f}", border=1, ln=True)

    pdf.ln(4)
    pdf.cell(130, 8, f"Subtotal:", align="R")
    pdf.cell(30, 8, f"₹{subtotal:.2f}", ln=True)

    pdf.cell(130, 8, f"Discount:", align="R")
    pdf.cell(30, 8, f"-₹{discount_val:.2f}", ln=True)

    pdf.cell(130, 10, f"Total:", align="R")
    pdf.cell(30, 10, f"₹{total:.2f}", ln=True)

    outpath = f"receipt_{order_id}.pdf"
    pdf.output(outpath)

    return outpath

# -------------------------
# App Navigation
# -------------------------
PAGES = {
    "Order": "order",
    "Add Product": "add_product",
    "Orders Report": "report"
}
page = st.sidebar.radio("Menu", list(PAGES.keys()))

# -------------------------
# PAGE: Order
# -------------------------
if page == "Order":
    st.title("🛒 Product Order System (No Images)")

    c1, c2 = st.columns([3, 1])
    with c1:
        q = st.text_input("Search product", value="")
    with c2:
        cat = st.selectbox("Category", ["All"] + sorted(df["Category"].unique()))

    mask = df["Product"].str.contains(q, case=False, na=False) | df["ProductList"].str.contains(q, case=False, na=False)
    if cat != "All":
        mask &= df["Category"] == cat

    filtered = df[mask].reset_index(drop=True)

    st.subheader("Available products")

    cols_per_row = 2
    for i in range(0, len(filtered), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(filtered):
                break

            prod = filtered.iloc[idx]
            with col:
                st.markdown(f"### {prod['Product']}")
                st.write(f"Supplier: {prod['Supplier']}")
                st.write(f"Price: ₹{prod['Price']:.2f}")

                # weight input only if applicable
                show_weight = weight_applicable_for_row(prod["ProductList"])

                weight_str = ""
                if show_weight:
                    # numeric input + unit selector
                    w_val = st.number_input(f"Weight (numeric) - {prod['Product']}", min_value=0.0, value=500.0, step=50.0, key=f"wval_{idx}")
                    w_unit = st.selectbox("Unit", ["g", "kg", "ml"], index=0, key=f"wunit_{idx}")
                    # Convert display: if user selects kg and enters e.g. 1 -> show "1kg"
                    # If they enter a decimal and choose g, we format integer
                    if w_unit == "g":
                        w_display = f"{int(w_val)}g"
                    else:
                        # allow decimal for kg or ml
                        if float(w_val).is_integer():
                            w_display = f"{int(w_val)}{w_unit}"
                        else:
                            w_display = f"{w_val}{w_unit}"
                    weight_str = w_display
                else:
                    st.info("Weight not applicable for this item.")

                qty_key = f"qty_{idx}"
                qty = st.number_input("Qty", min_value=1, value=1, key=qty_key)

                if st.button("Add to Cart", key=f"add_{idx}"):
                    add_to_cart(prod["Product"], prod["Supplier"], prod["Price"], qty, weight_str)
                    st.success(f"Added {prod['Product']} x{qty}" + (f" ({weight_str})" if weight_str else ""))

    # CART SIDEBAR
    st.sidebar.header("🧾 Current Cart")

    if st.session_state.cart:
        df_cart = pd.DataFrame(st.session_state.cart)
        st.sidebar.table(df_cart[["Product", "Weight", "Price", "Qty", "LineTotal"]])

        discount_pct = st.sidebar.number_input("Discount %", min_value=0.0, max_value=100.0, value=0.0, step=0.5)

        subtotal, discount_val, total = compute_cart_totals(discount_pct=discount_pct)

        st.sidebar.write(f"Subtotal: ₹{subtotal:.2f}")
        st.sidebar.write(f"Discount: -₹{discount_val:.2f}")
        st.sidebar.write(f"Total: ₹{total:.2f}")

        if st.sidebar.button("Save Order"):
            order_id, df_saved = save_order(st.session_state.cart, discount_pct)

            receipt_path = create_pdf_receipt(order_id, df_saved, subtotal, discount_val, total) if FPDF_AVAILABLE else None

            clear_cart()

            st.sidebar.success(f"Order {order_id} saved.")

            # Download receipt or CSV
            if receipt_path:
                st.sidebar.download_button(
                    "Download Receipt (PDF)",
                    data=open(receipt_path, "rb").read(),
                    file_name=receipt_path,
                    mime="application/pdf"
                )
            else:
                st.sidebar.download_button(
                    "Download Order (CSV)",
                    data=df_saved.to_csv(index=False),
                    file_name=f"order_{order_id}.csv",
                    mime="text/csv"
                )

    else:
        st.sidebar.info("Cart is empty")

# -------------------------
# PAGE: Add Product
# -------------------------
elif page == "Add Product":
    st.title("➕ Add New Product")
    st.write("Add a new product to the product_template.xlsx file. Use ProductList token to control category (e.g., Bread_Product_1_Name).")

    p_productlist = st.text_input("ProductList (e.g., Milk_Product_1_CheeseMozarella)")
    p_name = st.text_input("Product Name")
    p_supplier = st.text_input("Supplier")
    p_price = st.number_input("Price", min_value=0.0, value=0.0)

    if st.button("Add Product"):
        if not p_productlist:
            st.error("ProductList is required.")
        else:
            df_existing = pd.read_excel(PRODUCT_FILE)
            new_row = {
                "ProductList": p_productlist,
                "Product": p_name or p_productlist,
                "Supplier": p_supplier,
                "Price": p_price
            }
            df_existing = pd.concat([df_existing, pd.DataFrame([new_row])], ignore_index=True)
            df_existing.to_excel(PRODUCT_FILE, index=False)
            st.success("Product added successfully! Refresh app if necessary.")

# -------------------------
# PAGE: Orders Report
# -------------------------
elif page == "Orders Report":
    st.title("📊 Orders Report")

    if os.path.exists(ORDER_FILE):
        df_orders = pd.read_excel(ORDER_FILE)
        st.dataframe(df_orders)

        # Ensure Timestamp is datetime if possible
        try:
            df_orders["Timestamp"] = pd.to_datetime(df_orders["Timestamp"])
        except Exception:
            pass

        # Daily summary (by date portion of Timestamp)
        if "Timestamp" in df_orders.columns:
            df_orders["DateOnly"] = pd.to_datetime(df_orders["Timestamp"].dt.date)
            daily = df_orders.groupby("DateOnly").agg({
                "LineTotal": "sum",
                "OrderID": pd.Series.nunique
            }).rename(columns={"LineTotal": "Revenue", "OrderID": "Orders"})
            st.subheader("Daily Summary")
            st.table(daily.sort_index(ascending=False).head(30))

        st.download_button(
            "Download Orders (Excel)",
            data=open(ORDER_FILE, "rb").read(),
            file_name="orders.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No orders yet.")

# -------------------------
# Sidebar footer
# -------------------------
st.sidebar.markdown("---")
st.sidebar.write("App created. Weight field added (excluded: Bread_Product, Packing_Product). PDF support: " + ("Yes" if FPDF_AVAILABLE else "No"))
