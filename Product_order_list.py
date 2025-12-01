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
# Config / Files / Folders
# -------------------------
st.set_page_config(page_title="Product Order System", layout="wide", page_icon="🛒")

PRODUCT_FILE = "product_template.xlsx"
ORDER_FILE = "orders.xlsx"


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
                "Sauces_Product_6_Tomato ketchup"
            ],
            "Product Name": ["Cheese Mozorella", "Butter", "Pizza Base 10 inch", "Tomato ketchup"],
            "Supplier": ["Blink IT", "Blink IT", "Baker's Hub", "Sauce Co."],
            "Price": [535.0, 290.0, 120.0, 60.0]
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
        supplier_col = df.columns[0]

    if price_col is None:
        numeric_cols = df.select_dtypes(include=["number"]).columns
        price_col = numeric_cols[0] if len(numeric_cols) else df.columns[0]

    df = df.rename(columns={
        product_col: "ProductList",
        name_col: "Product",
        supplier_col: "Supplier",
        price_col: "Price"
    })

    if "Supplier" not in df.columns:
        df["Supplier"] = ""

    if "Price" not in df.columns:
        df["Price"] = 0

    def extract_category(x):
        s = str(x)
        if "_" in s:
            return s.split("_")[0]
        return "General"

    df["Category"] = df["ProductList"].apply(extract_category)

    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0.0)

    return df


df = load_products()


# -------------------------
# Cart & Helpers
# -------------------------
if "cart" not in st.session_state:
    st.session_state.cart = []

def add_to_cart(product, supplier, price, qty):
    st.session_state.cart.append({
        "OrderID": None,
        "Product": product,
        "Supplier": supplier,
        "Price": float(price),
        "Qty": int(qty),
        "LineTotal": float(price) * int(qty)
    })

def clear_cart():
    st.session_state.cart = []

def compute_cart_totals(discount_pct=0.0):
    dfc = pd.DataFrame(st.session_state.cart) if st.session_state.cart else pd.DataFrame(columns=["LineTotal"])
    subtotal = dfc["LineTotal"].sum() if not dfc.empty else 0.0
    discount_val = subtotal * (discount_pct / 100)
    return subtotal, discount_val, subtotal - discount_val

def save_order(cart, discount_pct=0.0):
    order_id = str(uuid.uuid4()).split("-")[0].upper()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for line in cart:
        rows.append({
            "OrderID": order_id,
            "Timestamp": now,
            "Product": line["Product"],
            "Supplier": line["Supplier"],
            "Price": line["Price"],
            "Qty": line["Qty"],
            "LineTotal": line["LineTotal"],
            "DiscountPct": discount_pct
        })

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
    pdf.ln(4)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(80, 8, "Product", border=1)
    pdf.cell(30, 8, "Price", border=1)
    pdf.cell(20, 8, "Qty", border=1)
    pdf.cell(30, 8, "Total", border=1, ln=True)

    pdf.set_font("Arial", size=11)
    for _, r in df_order.iterrows():
        pdf.cell(80, 8, str(r["Product"])[:28], border=1)
        pdf.cell(30, 8, f"₹{r['Price']:.2f}", border=1)
        pdf.cell(20, 8, str(int(r["Qty"])), border=1)
        pdf.cell(30, 8, f"₹{r['LineTotal']:.2f}", border=1, ln=True)

    pdf.ln(4)
    pdf.cell(130, 8, "Subtotal:", align="R")
    pdf.cell(30, 8, f"₹{subtotal:.2f}", ln=True)

    pdf.cell(130, 8, "Discount:", align="R")
    pdf.cell(30, 8, f"-₹{discount_val:.2f}", ln=True)

    pdf.cell(130, 10, "Total:", align="R")
    pdf.cell(30, 10, f"₹{total:.2f}", ln=True)

    outpath = f"receipt_{order_id}.pdf"
    pdf.output(outpath)
    return outpath


# -------------------------
# Sidebar Menu
# -------------------------
PAGES = {
    "Order": "order",
    "Add Product": "add_product",
    "Orders Report": "report"
}
page = st.sidebar.radio("Menu", list(PAGES.keys()))

# -------------------------
# PAGE: ORDER
# -------------------------
if page == "Order":
    st.title("🛒 Product Order System")

    c1, c2 = st.columns([3, 1])
    with c1:
        q = st.text_input("Search product", value="")
    with c2:
        cat = st.selectbox("Category", ["All"] + sorted(df["Category"].unique()))

    mask = df["Product"].str.contains(q, case=False, na=False) | df["ProductList"].str.contains(q, case=False, na=False)
    if cat != "All":
        mask &= df["Category"] == cat

    filtered = df[mask].reset_index(drop=True)

    st.subheader("Available products (No images)")

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

                qty_key = f"qty_{idx}"
                qty = st.number_input("Qty", min_value=1, value=1, key=qty_key)

                if st.button("Add to Cart", key=f"add_{idx}"):
                    add_to_cart(prod["Product"], prod["Supplier"], prod["Price"], qty)
                    st.success(f"Added {prod['Product']} x{qty}")

    # CART
    st.sidebar.header("🧾 Cart")

    if st.session_state.cart:
        df_cart = pd.DataFrame(st.session_state.cart)
        st.sidebar.table(df_cart[["Product", "Price", "Qty", "LineTotal"]])

        discount_pct = st.sidebar.number_input("Discount %", min_value=0.0, max_value=100.0, value=0.0, step=0.5)

        subtotal, discount_val, total = compute_cart_totals(discount_pct)

        st.sidebar.write(f"Subtotal: ₹{subtotal:.2f}")
        st.sidebar.write(f"Discount: -₹{discount_val:.2f}")
        st.sidebar.write(f"Total: ₹{total:.2f}")

        if st.sidebar.button("Save Order"):
            order_id, df_saved = save_order(st.session_state.cart, discount_pct)

            receipt_path = create_pdf_receipt(order_id, df_saved, subtotal, discount_val, total)
            clear_cart()

            st.sidebar.success(f"Order {order_id} saved.")

            if receipt_path:
                st.sidebar.download_button(
                    "Download Receipt (PDF)",
                    data=open(receipt_path, "rb").read(),
                    file_name=receipt_path,
                    mime="application/pdf"
                )

    else:
        st.sidebar.info("Cart is empty")

# -------------------------
# PAGE: ADD PRODUCT
# -------------------------
elif page == "Add Product":
    st.title("➕ Add New Product")

    p_productlist = st.text_input("ProductList (e.g., Milk_Product_1_CheeseMozarella)")
    p_name = st.text_input("Product Name")
    p_supplier = st.text_input("Supplier")
    p_price = st.number_input("Price", min_value=0.0, value=0.0)

    if st.button("Add Product"):
        df_existing = pd.read_excel(PRODUCT_FILE)

        new_row = {
            "ProductList": p_productlist,
            "Product": p_name or p_productlist,
            "Supplier": p_supplier,
            "Price": p_price
        }

        df_existing = pd.concat([df_existing, pd.DataFrame([new_row])], ignore_index=True)
        df_existing.to_excel(PRODUCT_FILE, index=False)

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
        daily = df_orders.groupby(df_orders["Timestamp"].dt.date).agg({
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
