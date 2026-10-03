import streamlit as st
from supabase import create_client

URL = "https://lhmzzcowbcuqktppphjo.supabase.co"
KEY = "sb_publishable_9_O2cKROzkcqcmTTi_OrPg_OVRW4Va1"
supabase = create_client(URL, KEY)

st.set_page_config(page_title="StockClaro", page_icon="📦")
st.title("📦 StockClaro")

menu = st.sidebar.selectbox("Menú", ["Inventario", "Agregar", "Movimiento"])

if menu == "Inventario":
    busc = st.text_input("🔍 Buscar producto")
    data = supabase.table("productos").select("*").execute().data or []
    if busc:
        data = [p for p in data if busc.lower() in p['nombre'].lower()]
    for p in data:
        icono = "🔴" if p['stock'] <= p['stock_minimo'] else "🟢"
        st.write(f"{icono} **{p['nombre']}** | Stock: {p['stock']} | ${p['precio_venta']}")

elif menu == "Agregar":
    n = st.text_input("Nombre")
    pc = st.number_input("Precio compra", 0.0)
    pv = st.number_input("Precio venta", 0.0)
    s = st.number_input("Stock", 0, step=1)
    sm = st.number_input("Stock mínimo", 5, step=1)
    if st.button("Guardar"):
        if n:
            supabase.table("productos").insert({"nombre": n, "precio_compra": pc, "precio_venta": pv, "stock": s, "stock_minimo": sm}).execute()
            st.success("Guardado ✅")
        else:
            st.error("Pon nombre")

else:
    prods = supabase.table("productos").select("*").execute().data or []
    d = {p['nombre']: p for p in prods}
    if d:
        sel = st.selectbox("Producto", list(d.keys()))
        tipo = st.selectbox("Tipo", ["entrada", "salida"])
        cant = st.number_input("Cantidad", 1, step=1)
        if st.button("Registrar"):
            p = d[sel]
            ns = p['stock'] + cant if tipo=="entrada" else p['stock'] - cant
            if ns < 0:
                st.error("Sin stock suficiente")
            else:
                supabase.table("productos").update({"stock": ns}).eq("id", p['id']).execute()
                supabase.table("movimientos").insert({"producto_id": p['id'], "tipo": tipo, "cantidad": cant}).execute()
                st.success(f"Listo. Nuevo stock: {ns}")
    else:
        st.info("Primero agrega un producto")