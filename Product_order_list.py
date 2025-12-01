import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
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
IMAGE_FOLDER = "generated_images"

os.makedirs(IMAGE_FOLDER, exist_ok=True)


# -------------------------
# Utility: safe text size
# -------------------------
def get_text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[float, float]:
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        return w, h

    if hasattr(draw, "textlength"):
        w = draw.textlength(text, font=font)
        h = font.getmetrics()[0] if hasattr(font, "getmetrics") else 12
        return w, h

    return (len(text) * 7, 12)


# -------------------------
# Generate placeholder image (JPG update)
# -------------------------
def generate_placeholder(product_name: str) -> str:
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in product_name).strip()

    # Force JPG output
    img_path = os.path.join(IMAGE_FOLDER, f"{safe_name}.jpg")

    # Already exists? Just return.
    if os.path.exists(img_path):
        return img_path

    width, height = 360, 240
    bg_color = (245, 245, 245)
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    name = str(product_name)
    w, h = get_text_size(draw, name, font)

    # If text too long, split into 2 lines
    if w > (width - 20):
        parts = name.split()
        mid = len(parts) // 2
        line1 = " ".join(parts[:mid])
        line2 = " ".join(parts[mid:])
        w1, h1 = get_text_size(draw, line1, font)
        w2, h2 = get_text_size(draw, line2, font)

        draw.text(((width - w1) / 2, (height / 2) - h1 - 4), line1, font=font, fill="black")
        draw.text(((width - w2) / 2, (height / 2) + 4), line2, font=font, fill="black")
    else:
        draw.text(((width - w) / 2, (height - h) / 2), name, font=font, fill="black")

    draw.rectangle([1, 1, width - 2, height - 2], outline=(220, 220, 220))

    # Save as high-quality JPG
    img.save(img_path, format="JPEG", quality=92)

    return img_path


# -------------------------
# Load products with auto-detect
# -------------------------
@st.cache_data
def load_products(product_file=PRODUCT_FILE):

    df = pd.read_excel(product_file)

    # Remove duplicate columns
    df = df.loc[:, ~df.columns.duplicated()]

    # Ensure required columns exist
    required_cols = [
        "Product No",
        "Product",
        "ProductList",
        "Supplier",
        "Price",
        "Category",
        "CategoryDisplay"
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)

    # Extract category
    def extract_cat(x):
        s = str(x)
        if "_" in s:
            return s.split("_")[0]
        return "General"

    df["Category"] = df["ProductList"].apply(extract_cat)
    df["CategoryDisplay"] = df["Category"]

    # 🟩 ADD THIS — generate JPG image placeholders
    df["Image"] = df["Product"].astype(str).apply(generate_placeholder)

    return df


# -------------------------
# Cart & helpers
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
    discount_val = subtotal * (discount_pct / 100.0)
    total = subtotal - discount_val
    return subtotal, discount_val, total

def save_order(cart, discount_pct=0.0):
    order_id = str(uuid.uuid4()).split("-")[0].upper()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for line in cart:
        row = {
            "OrderID": order_id,
            "Timestamp": now,
            "Product": line["Product"],
            "Supplier": line.get("Supplier", ""),
            "Price": line["Price"],
            "Qty": line["Qty"],
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
    pdf.cell(200, 6, txt=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(4)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(80, 8, "Product", border=1)
    pdf.cell(30, 8, "Price", border=1)
    pdf.cell(20, 8, "Qty", border=1)
    pdf.cell(30, 8, "LineTotal", border=1, ln=True)

    pdf.set_font("Arial", size=11)
    for _, r in df_order.iterrows():
        pdf.cell(80, 8, str(r["Product"])[:35], border=1)
        pdf.cell(30, 8, f"₹{r['Price']:.2f}", border=1)
        pdf.cell(20, 8, str(int(r["Qty"])), border=1)
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
    st.title("🛒 Product Order System")

    c1, c2 = st.columns([3, 1])
    with c1:
        q = st.text_input("Search product", value="")
    with c2:
        cat = st.selectbox("Category", ["All"] + sorted(df["Category"].unique().tolist()))

    mask = df["Product"].str.contains(q, case=False, na=False) | \
       df["ProductList"].str.contains(q, case=False, na=False)
    if cat != "All":
        mask &= df["Category"] == cat

    filtered = df[mask].reset_index(drop=True)

    st.subheader("Available products")
    cols_per_row = 3

    for i in range(0, len(filtered), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(filtered):
                break

            prod = filtered.iloc[idx]
            with col:
                st.image(prod["Image"], use_container_width=True)
                st.markdown(f"**{prod['Product']}**")
                st.write(f"Supplier: {prod['Supplier']}")
                st.write(f"Price: ₹{prod['Price']:.2f}")

                qty_key = f"qty_{idx}"
                qty = st.number_input("Qty", min_value=1, value=1, key=qty_key)

                if st.button("Add to Cart", key=f"add_{idx}"):
                    add_to_cart(prod["Product"], prod["Supplier"], prod["Price"], qty)
                    st.success(f"Added {prod['Product']} (x{qty})")

    # CART SIDEBAR
    st.sidebar.header("🧾 Current Cart")

    if st.session_state.cart:
        df_cart = pd.DataFrame(st.session_state.cart)
        st.sidebar.table(df_cart[["Product", "Price", "Qty", "LineTotal"]])

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
    st.write("Add a new product to the product_template.xlsx file.")

    p_productlist = st.text_input("ProductList (e.g., Milk_Product_1_CheeseMozarella)")
    p_name = st.text_input("Product Name")
    p_supplier = st.text_input("Supplier")
    p_price = st.number_input("Price", min_value=0.0, value=0.0, step=0.5)

    if st.button("Add Product to Excel"):
        if not p_productlist:
            st.error("ProductList field required.")
        else:
            df_existing = pd.read_excel(PRODUCT_FILE)

            new_row = {
                "ProductList": p_productlist,
                "Product": p_name or p_productlist,
                "Supplier": p_supplier,
                "Price": p_price
            }

            # Ensure correct column mapping
            row_to_save = {}
            for col in df_existing.columns:
                if "product" in col.lower() and "list" in col.lower():
                    row_to_save[col] = p_productlist
                elif "name" in col.lower():
                    row_to_save[col] = p_name or p_productlist
                elif "supplier" in col.lower():
                    row_to_save[col] = p_supplier
                elif "price" in col.lower():
                    row_to_save[col] = p_price
                else:
                    row_to_save[col] = ""

            df_existing = df_existing.append(row_to_save, ignore_index=True)
            df_existing.to_excel(PRODUCT_FILE, index=False)

            generate_placeholder(p_name or p_productlist)

            st.success("Product added. Refresh the app to see it.")


# -------------------------
# PAGE: Orders Report
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

        if st.button("Download Orders (Excel)"):
            with open(ORDER_FILE, "rb") as f:
                st.download_button(
                    "Download full orders.xlsx",
                    data=f,
                    file_name="orders.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.info("No orders yet.")


# -------------------------
# Sidebar footer
# -------------------------
st.sidebar.markdown("---")
st.sidebar.write("App created: JPG image support added. PDF support:" + (" Yes" if FPDF_AVAILABLE else " No"))







