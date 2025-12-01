import streamlit as st
import pandas as pd
import os
from datetime import datetime
import uuid

# Optional PDF library
try:
    from fpdf import FPDF
    PDF_OK = True
except:
    PDF_OK = False

st.set_page_config(page_title="Product Order System", layout="wide", page_icon="🛒")

PRODUCT_FILE = "product_template.xlsx"
ORDER_FILE = "orders.xlsx"


# -------------------------
# LOAD PRODUCTS
# -------------------------
@st.cache_data
def load_products():

    df = pd.read_excel(PRODUCT_FILE)

    # Clean column names
    df.columns = df.columns.str.strip()

    required_cols = [
        "Product",
        "ProductList",
        "Supplier",
        "Price",
        "Category",
        "CategoryDisplay",
        "Product No",
        "Image"  # REQUIRED for images
    ]

    # Add missing columns
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    # Price numeric
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)

    # Extract category if blank
    def extract_category(x):
        s = str(x)
        if "_" in s:
            return s.split("_")[0]
        return "General"

    df["Category"] = df["Category"].replace("", pd.NA)
    df["Category"] = df["Category"].fillna(df["ProductList"].apply(extract_category))

    # Category Display fallback
    df["CategoryDisplay"] = df["CategoryDisplay"].replace("", pd.NA)
    df["CategoryDisplay"] = df["CategoryDisplay"].fillna(df["Category"])

    return df


df = load_products()


# -------------------------
# CART LOGIC
# -------------------------
if "cart" not in st.session_state:
    st.session_state.cart = []


def add_to_cart(product, supplier, price, qty, weight):
    st.session_state.cart.append({
        "OrderID": None,
        "Product": product,
        "Supplier": supplier,
        "Price": float(price),
        "Qty": int(qty),
        "Weight": weight,
        "LineTotal": float(price) * int(qty)
    })


def clear_cart():
    st.session_state.cart = []


def compute_totals(discount_pct=0):
    dfc = pd.DataFrame(st.session_state.cart)
    if dfc.empty:
        return 0, 0, 0
    subtotal = dfc["LineTotal"].sum()
    discount = subtotal * (discount_pct / 100)
    total = subtotal - discount
    return subtotal, discount, total


def save_order(cart, discount_pct):
    order_id = str(uuid.uuid4()).split("-")[0].upper()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for c in cart:
        rows.append({
            "OrderID": order_id,
            "Timestamp": now,
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


def create_pdf(order_id, df_order, subtotal, discount_val, total):
    if not PDF_OK:
        return None

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, f"Receipt - Order {order_id}", ln=True, align="C")
    pdf.cell(200, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(70, 8, "Product", border=1)
    pdf.cell(20, 8, "Qty", border=1)
    pdf.cell(25, 8, "Weight", border=1)
    pdf.cell(30, 8, "Price", border=1)
    pdf.cell(30, 8, "Total", border=1, ln=True)

    pdf.set_font("Arial", size=11)
    for _, r in df_order.iterrows():
        pdf.cell(70, 8, r["Product"][:25], border=1)
        pdf.cell(20, 8, str(r["Qty"]), border=1)
        pdf.cell(25, 8, str(r["Weight"]), border=1)
        pdf.cell(30, 8, f"₹{r['Price']:.2f}", border=1)
        pdf.cell(30, 8, f"₹{r['LineTotal']:.2f}", border=1, ln=True)

    pdf.ln(5)
    pdf.cell(120, 8, "Subtotal:", align="R")
    pdf.cell(30, 8, f"₹{subtotal:.2f}", ln=True)
    pdf.cell(120, 8, "Discount:", align="R")
    pdf.cell(30, 8, f"₹{discount_val:.2f}", ln=True)
    pdf.cell(120, 10, "Total:", align="R")
    pdf.cell(30, 10, f"₹{total:.2f}", ln=True)

    out = f"receipt_{order_id}.pdf"
    pdf.output(out)
    return out


# -------------------------
# PAGE NAVIGATION
# -------------------------
page = st.sidebar.radio("Menu", ["Order", "Add Product", "Orders Report"])


# -------------------------
# PAGE: ORDER
# -------------------------
if page == "Order":

    st.title("🛒 Product Order System")

    col1, col2 = st.columns([3, 1])
    with col1:
        q = st.text_input("Search product")

    with col2:
        cat = st.selectbox(
            "Category",
            ["All"] + sorted(df["CategoryDisplay"].unique().tolist())
        )

    mask = (
        df["Product"].str.contains(q, case=False, na=False)
        | df["ProductList"].str.contains(q, case=False, na=False)
    )

    if cat != "All":
        mask &= df["CategoryDisplay"] == cat

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

                # -------------------------
                # IMAGE HANDLING (Same folder)
                # -------------------------
                image_file = str(prod["Image"]).strip()

                if image_file and os.path.exists(image_file):
                    st.image(image_file, use_container_width=True)
                elif image_file:
                    st.warning(f"Image not found: {image_file}")
                else:
                    st.info("No image")

                # -------------------------
                # PRODUCT INFO
                # -------------------------
                st.markdown(f"### {prod['Product']}")
                st.write(f"Supplier: {prod['Supplier']}")
                st.write(f"Price: ₹{prod['Price']:.2f}")

                qty = st.number_input(f"Qty-{idx}", min_value=1, value=1)

                # -------------------------
                # WEIGHT LOGIC
                # -------------------------
                category_value = str(prod["Category"]).strip().lower()
                no_weight_categories = ["bread_product", "packing_product"]

                if category_value in no_weight_categories:
                    weight = ""
                    st.write("Weight: Not required")
                else:
                    weight = st.text_input(f"Weight-{idx}", placeholder="500g / 1kg")

                if st.button("Add to Cart", key=f"add_{idx}"):
                    add_to_cart(prod["Product"], prod["Supplier"], prod["Price"], qty, weight)
                    st.success(f"Added {prod['Product']}")

    # -------------------------
    # CART SIDEBAR
    # -------------------------
    st.sidebar.header("🧾 Cart")

    if st.session_state.cart:

        df_cart = pd.DataFrame(st.session_state.cart)
        st.sidebar.table(df_cart[["Product", "Qty", "Weight", "Price", "LineTotal"]])

        discount_pct = st.sidebar.number_input(
            "Discount %", min_value=0.0, max_value=100.0, value=0.0
        )

        subtotal, disc, total = compute_totals(discount_pct)

        st.sidebar.write(f"Subtotal: ₹{subtotal:.2f}")
        st.sidebar.write(f"Discount: ₹{disc:.2f}")
        st.sidebar.write(f"Total: ₹{total:.2f}")

        if st.sidebar.button("Save Order"):
            order_id, df_saved = save_order(st.session_state.cart, discount_pct)
            pdf_path = create_pdf(order_id, df_saved, subtotal, disc, total)

            clear_cart()
            st.success(f"Order {order_id} saved!")

            if pdf_path:
                st.download_button(
                    "Download Receipt (PDF)",
                    data=open(pdf_path, "rb").read(),
                    file_name=pdf_path,
                    mime="application/pdf"
                )
            else:
                st.download_button(
                    "Download Order CSV",
                    data=df_saved.to_csv(index=False),
                    file_name=f"order_{order_id}.csv"
                )

    else:
        st.sidebar.info("Cart is empty.")


# -------------------------
# PAGE: ADD PRODUCT
# -------------------------
elif page == "Add Product":

    st.title("➕ Add New Product")

    p_list = st.text_input("ProductList (e.g., Milk_Product_1_Cheese)")
    p_name = st.text_input("Product Name")
    p_supplier = st.text_input("Supplier")
    p_price = st.number_input("Price", min_value=0.0)
    p_image = st.text_input("Image File Name (optional, e.g., Cheese.jpg)")

    if st.button("Add Product"):
        if not p_list:
            st.error("ProductList is required")
        else:
            df_old = pd.read_excel(PRODUCT_FILE)
            new_row = {
                "ProductList": p_list,
                "Product": p_name or p_list,
                "Supplier": p_supplier,
                "Price": p_price,
                "Image": p_image
            }
            df_out = pd.concat([df_old, pd.DataFrame([new_row])], ignore_index=True)
            df_out.to_excel(PRODUCT_FILE, index=False)
            st.success("Product added successfully!")


# -------------------------
# PAGE: ORDERS REPORT
# -------------------------
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
        st.info("No orders found.")


# FOOTER
st.sidebar.markdown("---")
st.sidebar.write(f"PDF Enabled: {'Yes' if PDF_OK else 'No'}")
