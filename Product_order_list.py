import streamlit as st
import pandas as pd
import os
import uuid
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="Product Order System", layout="wide")

PRODUCT_FILE = "product_template.xlsx"
ORDER_FILE = "orders.xlsx"
IMAGE_FOLDER = "product_images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)


# ------------------------------------------------------
# IMAGE PLACEHOLDER GENERATOR
# ------------------------------------------------------
def generate_placeholder(product_name):
    """Generate a JPG placeholder image for a product."""
    img = Image.new("RGB", (600, 400), color=(235, 235, 235))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except:
        font = ImageFont.load_default()

    text = product_name[:25]
    draw.text((20, 180), text, fill=(0, 0, 0), font=font)

    filename = f"{IMAGE_FOLDER}/{product_name.replace(' ','_')}.jpg"
    img.save(filename, "JPEG")

    return filename


# ------------------------------------------------------
# LOAD PRODUCT DATA
# ------------------------------------------------------
@st.cache_data
def load_products():
    required_cols = [
        "Product No", "Product", "ProductList",
        "Supplier", "Price", "Category", "CategoryDisplay"
    ]

    # Load Excel
    df = pd.read_excel(PRODUCT_FILE)

    # Remove duplicate columns
    df = df.loc[:, ~df.columns.duplicated()]

    # Normalize names
    rename_map = {
        "productname": "Product",
        "product_list": "ProductList",
        "productlist": "ProductList",
    }
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={c.lower(): rename_map.get(c.lower(), c) for c in df.columns})

    # Ensure required columns exist
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    # Convert price
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)

    # Extract Category from ProductList
    def extract_cat(x):
        s = str(x)
        return s.split("_")[0] if "_" in s else "General"

    df["Category"] = df["ProductList"].apply(extract_cat)
    df["CategoryDisplay"] = df["Category"]

    # Generate / assign images
    df["Image"] = df["Product"].astype(str).apply(generate_placeholder)

    return df


df = load_products()


# ------------------------------------------------------
# CART MANAGEMENT
# ------------------------------------------------------
if "cart" not in st.session_state:
    st.session_state.cart = []


def add_to_cart(p, s, price, qty, weight):
    st.session_state.cart.append({
        "Product": p,
        "Supplier": s,
        "Price": float(price),
        "Qty": int(qty),
        "Weight": weight,
        "LineTotal": float(price) * int(qty)
    })


def clear_cart():
    st.session_state.cart = []


def compute_totals(discount_pct):
    if not st.session_state.cart:
        return 0, 0, 0

    dfc = pd.DataFrame(st.session_state.cart)
    subtotal = dfc["LineTotal"].sum()
    disc = subtotal * (discount_pct / 100)
    total = subtotal - disc
    return subtotal, disc, total


def save_order(cart, discount_pct):
    order_id = str(uuid.uuid4()).split("-")[0].upper()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for c in cart:
        rows.append({
            "OrderID": order_id,
            "Timestamp": ts,
            "Product": c["Product"],
            "Supplier": c["Supplier"],
            "Price": c["Price"],
            "Qty": c["Qty"],
            "Weight": c["Weight"],
            "LineTotal": c["LineTotal"],
            "DiscountPct": discount_pct
        })

    df_new = pd.DataFrame(rows)

    if os.path.exists(ORDER_FILE):
        df_old = pd.read_excel(ORDER_FILE)
        df_out = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_out = df_new

    df_out.to_excel(ORDER_FILE, index=False)

    return order_id, df_new


# ------------------------------------------------------
# PAGE NAVIGATION
# ------------------------------------------------------
page = st.sidebar.radio("Menu", ["Order", "Add Product", "Orders Report"])


# ------------------------------------------------------
# PAGE 1: ORDER PAGE
# ------------------------------------------------------
if page == "Order":
    st.title("🛒 Product Order System")

    col1, col2 = st.columns([3, 1])
    with col1:
        q = st.text_input("Search Product")
    with col2:
        cat = st.selectbox("Category", ["All"] + sorted(df["Category"].unique().tolist()))

    # Filter logic
    mask = df["Product"].str.contains(q, case=False, na=False) | \
           df["ProductList"].str.contains(q, case=False, na=False)

    if cat != "All":
        mask &= df["Category"] == cat

    filtered = df[mask]

    st.subheader("Available Products")
    cols_per_row = 3

    for i in range(0, len(filtered), cols_per_row):
        row = st.columns(cols_per_row)
        for j, col in enumerate(row):
            idx = i + j
            if idx >= len(filtered):
                break

            prod = filtered.iloc[idx]

            with col:
                st.image(prod["Image"], use_container_width=True)
                st.markdown(f"### {prod['Product']}")
                st.write(f"Supplier: {prod['Supplier']}")
                st.write(f"Price: ₹{prod['Price']:.2f}")

                qty = st.number_input(f"Qty-{idx}", min_value=1, value=1)

                weight = ""
                if prod["Category"] not in ["Bread", "Packing"]:
                    weight = st.text_input(f"Weight-{idx}", placeholder="500g / 1kg")

                if st.button("Add to Cart", key=f"add_{idx}"):
                    add_to_cart(prod["Product"], prod["Supplier"], prod["Price"], qty, weight)
                    st.success("Added to cart")

    # CART SIDEBAR
    st.sidebar.header("🧾 Cart")

    if st.session_state.cart:
        df_cart = pd.DataFrame(st.session_state.cart)
        st.sidebar.table(df_cart)

        discount_pct = st.sidebar.number_input("Discount %", min_value=0.0, max_value=100.0, value=0.0)
        subtotal, disc, total = compute_totals(discount_pct)

        st.sidebar.write(f"Subtotal: ₹{subtotal:.2f}")
        st.sidebar.write(f"Discount: ₹{disc:.2f}")
        st.sidebar.write(f"Total: ₹{total:.2f}")

        if st.sidebar.button("Save Order"):
            order_id, saved = save_order(st.session_state.cart, discount_pct)
            clear_cart()
            st.success(f"Order {order_id} saved!")
    else:
        st.sidebar.info("Cart is empty.")


# ------------------------------------------------------
# PAGE 2: ADD PRODUCT
# ------------------------------------------------------
elif page == "Add Product":
    st.title("➕ Add New Product")

    pn = st.text_input("Product No")
    pl = st.text_input("ProductList")
    p = st.text_input("Product")
    s = st.text_input("Supplier")
    price = st.number_input("Price", min_value=0.0)

    if st.button("Add Product Now"):
        df_old = pd.read_excel(PRODUCT_FILE)

        new_row = {
            "Product No": pn,
            "ProductList": pl,
            "Product": p,
            "Supplier": s,
            "Price": price,
            "Category": pl.split("_")[0] if "_" in pl else "",
            "CategoryDisplay": pl.split("_")[0] if "_" in pl else "",
        }

        df_new = pd.concat([df_old, pd.DataFrame([new_row])], ignore_index=True)
        df_new.to_excel(PRODUCT_FILE, index=False)

        st.success("Product Added Successfully!")


# ------------------------------------------------------
# PAGE 3: REPORT PAGE
# ------------------------------------------------------
elif page == "Orders Report":
    st.title("📊 Orders Report")

    if os.path.exists(ORDER_FILE):
        df_orders = pd.read_excel(ORDER_FILE)
        st.dataframe(df_orders)

        df_orders["Timestamp"] = pd.to_datetime(df_orders["Timestamp"])
        daily = df_orders.groupby(df_orders["Timestamp"].dt.date).agg(
            Revenue=("LineTotal", "sum"),
            Orders=("OrderID", pd.Series.nunique)
        )

        st.subheader("Daily Summary")
        st.table(daily)

        st.download_button(
            "Download Orders Excel",
            data=open(ORDER_FILE, "rb").read(),
            file_name="orders.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.info("No orders found yet.")
